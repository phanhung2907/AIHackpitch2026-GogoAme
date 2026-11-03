"""Authentication, CSRF, Origin, and RBAC dependencies for FastAPI routes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import AuthSession, PreauthSession, StaffUser
from app.security.crypto import derive_csrf_token, sha256_bytes, verify_csrf_token
from app.security.rate_limit import rate_limiter

PREAUTH_COOKIE_NAME = "taporder_preauth"
STAFF_COOKIE_NAME = "taporder_staff"
GUEST_COOKIE_NAME = "taporder_guest"

PREAUTH_TTL_SECONDS = 10 * 60
STAFF_TTL_SECONDS = 8 * 3600
GUEST_TTL_SECONDS = 12 * 3600


@dataclass(frozen=True)
class StaffPrincipal:
    session_id: uuid.UUID
    raw_token: str
    user_id: uuid.UUID
    username: str
    role: str
    expires_at: datetime
    csrf_token: str


@dataclass(frozen=True)
class GuestPrincipal:
    session_id: uuid.UUID
    raw_token: str
    expires_at: datetime
    csrf_token: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def verify_exact_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    if not origin:
        raise AppError(
            status_code=403,
            code="ORIGIN_INVALID",
            message="Thiếu hoặc sai header Origin cho thao tác thay đổi dữ liệu.",
            details={},
        )
    normalized = origin.strip().rstrip("/")
    if normalized not in get_settings().allowed_origins_set:
        raise AppError(
            status_code=403,
            code="ORIGIN_INVALID",
            message="Origin không nằm trong danh sách cho phép.",
            details={},
        )


def require_preauth_csrf(request: Request, db: Session) -> tuple[str, PreauthSession]:
    verify_exact_origin(request)
    raw_token = request.cookies.get(PREAUTH_COOKIE_NAME)
    if not raw_token:
        raise AppError(
            status_code=403,
            code="CSRF_INVALID",
            message="Phiên pre-auth không tồn tại hoặc đã hết hạn.",
            details={},
        )
    token_hash = sha256_bytes(raw_token)
    preauth = db.get(PreauthSession, token_hash)
    now = utc_now()
    if preauth is None or preauth.consumed_at is not None or preauth.expires_at <= now:
        raise AppError(
            status_code=403,
            code="CSRF_INVALID",
            message="Phiên pre-auth không hợp lệ hoặc đã được sử dụng.",
            details={},
        )
    verify_csrf_token(request.headers.get("X-CSRF-Token"), preauth.csrf_hash)
    return raw_token, preauth


def authenticate_staff(
    request: Request,
    db: Session,
    *,
    required_role: str | None = None,
    require_csrf: bool = False,
    rate_bucket: str = "read",
) -> StaffPrincipal:
    if require_csrf:
        verify_exact_origin(request)
    raw_token = request.cookies.get(STAFF_COOKIE_NAME)
    if not raw_token:
        raise AppError(
            status_code=401,
            code="SESSION_EXPIRED",
            message="Phiên đăng nhập nhân viên không tồn tại hoặc đã hết hạn.",
            details={},
        )
    token_hash = sha256_bytes(raw_token)
    stmt = (
        select(AuthSession, StaffUser)
        .join(StaffUser, AuthSession.staff_user_id == StaffUser.id)
        .where(AuthSession.token_hash == token_hash, AuthSession.kind == "staff")
    )
    row = db.execute(stmt).first()
    now = utc_now()
    if row is None:
        raise AppError(
            status_code=401,
            code="SESSION_EXPIRED",
            message="Phiên đăng nhập nhân viên không hợp lệ hoặc đã hết hạn.",
            details={},
        )
    auth_session, staff_user = row
    if (
        auth_session.revoked_at is not None
        or auth_session.expires_at <= now
        or not staff_user.active
    ):
        raise AppError(
            status_code=401,
            code="SESSION_EXPIRED",
            message="Phiên đăng nhập nhân viên đã hết hạn hoặc bị thu hồi.",
            details={},
        )
    if require_csrf:
        verify_csrf_token(request.headers.get("X-CSRF-Token"), auth_session.csrf_hash)
    if required_role is not None and staff_user.role != required_role:
        raise AppError(
            status_code=403,
            code="FORBIDDEN",
            message="Tài khoản không có quyền thực hiện thao tác này.",
            details={"required_role": required_role},
        )

    if rate_bucket == "mutation":
        rate_limiter.check(f"staff_mut:{auth_session.id}", limit=60, window_seconds=60.0)
    elif rate_bucket == "read":
        rate_limiter.check(f"staff_read:{auth_session.id}", limit=120, window_seconds=60.0)

    csrf_token = derive_csrf_token(
        raw_token, "staff", str(auth_session.id), get_settings().session_secret
    )
    return StaffPrincipal(
        session_id=auth_session.id,
        raw_token=raw_token,
        user_id=staff_user.id,
        username=staff_user.username,
        role=staff_user.role,
        expires_at=auth_session.expires_at,
        csrf_token=csrf_token,
    )


def authenticate_guest(
    request: Request,
    db: Session,
    *,
    require_csrf: bool = False,
    rate_bucket: str = "read",
) -> GuestPrincipal:
    if require_csrf:
        verify_exact_origin(request)
    raw_token = request.cookies.get(GUEST_COOKIE_NAME)
    if not raw_token:
        raise AppError(
            status_code=401,
            code="SESSION_EXPIRED",
            message="Phiên khách không tồn tại hoặc đã hết hạn.",
            details={},
        )
    token_hash = sha256_bytes(raw_token)
    stmt = select(AuthSession).where(
        AuthSession.token_hash == token_hash, AuthSession.kind == "guest"
    )
    auth_session = db.execute(stmt).scalar_one_or_none()
    now = utc_now()
    if (
        auth_session is None
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
    ):
        raise AppError(
            status_code=401,
            code="SESSION_EXPIRED",
            message="Phiên khách đã hết hạn hoặc không hợp lệ.",
            details={},
        )
    if require_csrf:
        verify_csrf_token(request.headers.get("X-CSRF-Token"), auth_session.csrf_hash)

    if rate_bucket == "order":
        rate_limiter.check(f"guest_order:{auth_session.id}", limit=10, window_seconds=60.0)
    elif rate_bucket == "read":
        rate_limiter.check(f"guest_read:{auth_session.id}", limit=120, window_seconds=60.0)

    csrf_token = derive_csrf_token(
        raw_token, "guest", str(auth_session.id), get_settings().session_secret
    )
    return GuestPrincipal(
        session_id=auth_session.id,
        raw_token=raw_token,
        expires_at=auth_session.expires_at,
        csrf_token=csrf_token,
    )

