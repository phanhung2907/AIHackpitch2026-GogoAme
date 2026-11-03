"""F02 — Authentication, pre-auth CSRF bootstrap, staff login/session/logout."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import AuthSession, PreauthSession, StaffUser
from app.schemas import LoginInput
from app.security import (
    PREAUTH_COOKIE_NAME,
    PREAUTH_TTL_SECONDS,
    STAFF_COOKIE_NAME,
    STAFF_TTL_SECONDS,
    derive_csrf_token,
    generate_opaque_token,
    get_client_ip,
    rate_limiter,
    require_preauth_csrf,
    sha256_bytes,
    utc_now,
    verify_csrf_token,
    verify_dummy_password,
    verify_exact_origin,
    verify_password,
)
from app.services.common import append_audit_event, commit_or_translate, get_request_id, iso_utc


def bootstrap_preauth(request: Request, db: Session) -> tuple[str, dict[str, Any]]:
    """Issue or reuse valid 10-minute pre-authentication cookie and CSRF token."""
    ip = get_client_ip(request)
    rate_limiter.check(f"auth_bootstrap:{ip}", limit=30, window_seconds=60.0)

    settings = get_settings()
    now = utc_now()
    existing_raw = request.cookies.get(PREAUTH_COOKIE_NAME)
    if existing_raw:
        thash = sha256_bytes(existing_raw)
        existing = db.get(PreauthSession, thash)
        if existing is not None and existing.consumed_at is None and existing.expires_at > now:
            csrf_token = derive_csrf_token(existing_raw, "preauth", "login", settings.session_secret)
            return existing_raw, {
                "data": {
                    "csrf_token": csrf_token,
                    "expires_at": iso_utc(existing.expires_at),
                }
            }

    raw_token = generate_opaque_token()
    token_hash = sha256_bytes(raw_token)
    csrf_token = derive_csrf_token(raw_token, "preauth", "login", settings.session_secret)
    csrf_hash = sha256_bytes(csrf_token)
    expires_at = now + timedelta(seconds=PREAUTH_TTL_SECONDS)

    db.add(
        PreauthSession(
            token_hash=token_hash,
            csrf_hash=csrf_hash,
            created_at=now,
            expires_at=expires_at,
            consumed_at=None,
        )
    )
    commit_or_translate(db)
    return raw_token, {
        "data": {
            "csrf_token": csrf_token,
            "expires_at": iso_utc(expires_at),
        }
    }


def login_staff(
    request: Request, db: Session, payload: LoginInput
) -> tuple[str, dict[str, Any]]:
    """Verify preauth CSRF + Origin + credentials, rotate session, and audit login."""
    ip = get_client_ip(request)
    rate_limiter.check(f"login:{ip}:{payload.username}", limit=5, window_seconds=60.0)

    raw_preauth_token, _ = require_preauth_csrf(request, db)
    preauth_hash = sha256_bytes(raw_preauth_token)

    user = db.execute(
        select(StaffUser).where(StaffUser.username == payload.username)
    ).scalar_one_or_none()
    # Close read transaction before expensive Argon2 check so locks are not held
    db.rollback()

    if user is None:
        verify_dummy_password(payload.password)
        raise AppError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Tên đăng nhập hoặc mật khẩu không đúng.",
            details={},
        )

    if not verify_password(payload.password, user.password_hash) or not user.active:
        raise AppError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Tên đăng nhập hoặc mật khẩu không đúng.",
            details={},
        )

    now = utc_now()
    locked_preauth = db.execute(
        select(PreauthSession)
        .where(PreauthSession.token_hash == preauth_hash)
        .with_for_update()
    ).scalar_one_or_none()
    if (
        locked_preauth is None
        or locked_preauth.consumed_at is not None
        or locked_preauth.expires_at <= now
    ):
        db.rollback()
        raise AppError(
            status_code=403,
            code="CSRF_INVALID",
            message="Phiên pre-auth đã được sử dụng hoặc hết hạn.",
            details={},
        )

    locked_user = db.execute(
        select(StaffUser).where(StaffUser.id == user.id)
    ).scalar_one_or_none()
    if locked_user is None or not locked_user.active or locked_user.role not in {"barista", "cashier"}:
        db.rollback()
        raise AppError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Tên đăng nhập hoặc mật khẩu không đúng.",
            details={},
        )

    locked_preauth.consumed_at = now

    old_staff_raw = request.cookies.get(STAFF_COOKIE_NAME)
    if old_staff_raw:
        old_hash = sha256_bytes(old_staff_raw)
        old_sess = db.execute(
            select(AuthSession).where(
                AuthSession.token_hash == old_hash,
                AuthSession.kind == "staff",
            ).with_for_update()
        ).scalar_one_or_none()
        if old_sess is not None and old_sess.revoked_at is None:
            old_sess.revoked_at = now

    new_session_id = uuid.uuid4()
    new_raw_token = generate_opaque_token()
    new_token_hash = sha256_bytes(new_raw_token)
    settings = get_settings()
    new_csrf_token = derive_csrf_token(
        new_raw_token, "staff", str(new_session_id), settings.session_secret
    )
    new_csrf_hash = sha256_bytes(new_csrf_token)
    expires_at = now + timedelta(seconds=STAFF_TTL_SECONDS)

    new_sess = AuthSession(
        id=new_session_id,
        token_hash=new_token_hash,
        kind="staff",
        staff_user_id=locked_user.id,
        csrf_hash=new_csrf_hash,
        created_at=now,
        expires_at=expires_at,
        revoked_at=None,
    )
    db.add(new_sess)
    db.flush()

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="staff",
        principal_id=new_session_id,
        action="auth.login",
        resource_type="staff_user",
        resource_id=locked_user.id,
        before_state=None,
        after_state={"role": locked_user.role, "session_id": str(new_session_id)},
    )
    commit_or_translate(db)

    return new_raw_token, {
        "data": {
            "staff": {
                "id": str(locked_user.id),
                "username": locked_user.username,
                "role": locked_user.role,
            },
            "csrf_token": new_csrf_token,
            "expires_at": iso_utc(expires_at),
        }
    }


def logout_staff(request: Request, db: Session) -> None:
    """Revoke active staff session (requiring CSRF) or return 204 if already expired/missing with valid Origin."""
    verify_exact_origin(request)
    raw_token = request.cookies.get(STAFF_COOKIE_NAME)
    if not raw_token:
        return

    token_hash = sha256_bytes(raw_token)
    sess = db.execute(
        select(AuthSession)
        .where(AuthSession.token_hash == token_hash, AuthSession.kind == "staff")
        .with_for_update()
    ).scalar_one_or_none()
    now = utc_now()
    if sess is None or sess.revoked_at is not None or sess.expires_at <= now:
        db.rollback()
        return

    verify_csrf_token(request.headers.get("X-CSRF-Token"), sess.csrf_hash)
    sess.revoked_at = now
    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="staff",
        principal_id=sess.id,
        action="auth.logout",
        resource_type="session",
        resource_id=sess.id,
        before_state={"revoked": False},
        after_state={"revoked": True},
    )
    commit_or_translate(db)

