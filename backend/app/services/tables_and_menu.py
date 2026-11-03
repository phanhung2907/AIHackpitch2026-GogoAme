"""F01, F06, F10 — Guest QR bootstrap/join, menu snapshots, availability toggle, and QR export."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import read_event_watermark, repeatable_read_snapshot
from app.domain.totals import format_money_vnd
from app.errors import AppError
from app.models import AuthSession, Bill, DiningTable, MenuCategory, MenuItem
from app.schemas import AvailabilityInput, BootstrapGuestInput, JoinInput
from app.security import (
    GUEST_COOKIE_NAME,
    GUEST_TTL_SECONDS,
    GuestPrincipal,
    StaffPrincipal,
    decrypt_qr_token,
    derive_csrf_token,
    generate_opaque_token,
    get_client_ip,
    rate_limiter,
    sha256_bytes,
    utc_now,
    verify_exact_origin,
)
from app.services.common import (
    PendingDomainEvent,
    allocate_and_append_domain_events,
    append_audit_event,
    commit_or_translate,
    complete_idempotency_reservation,
    get_request_id,
    is_any_shift_open,
    iso_utc,
    parse_idempotency_key,
    reserve_or_replay_idempotency,
)


def resolve_enabled_table_by_qr(
    db: Session, qr_token: str, *, for_update: bool = False
) -> DiningTable:
    token_hash = sha256_bytes(qr_token)
    stmt = select(DiningTable).where(
        DiningTable.qr_token_hash == token_hash,
        DiningTable.enabled.is_(True),
    )
    if for_update:
        stmt = stmt.with_for_update()
    table = db.execute(stmt).scalar_one_or_none()
    if table is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Mã QR bàn không hợp lệ hoặc bàn đang tạm ngưng phục vụ.",
            details={},
        )
    return table


def bootstrap_guest(
    request: Request, db: Session, payload: BootstrapGuestInput
) -> tuple[str | None, dict[str, Any]]:
    """Resolve QR token, reuse or issue guest anonymous session cookie, and return table + current_bill_id."""
    ip = get_client_ip(request)
    rate_limiter.check(f"guest_bootstrap:{ip}", limit=30, window_seconds=60.0)
    verify_exact_origin(request)

    table = resolve_enabled_table_by_qr(db, payload.qr_token, for_update=False)
    current_bill_id = db.execute(
        select(Bill.id).where(Bill.table_id == table.id, Bill.status == "open")
    ).scalar_one_or_none()

    settings = get_settings()
    now = utc_now()
    existing_raw = request.cookies.get(GUEST_COOKIE_NAME)
    if existing_raw:
        thash = sha256_bytes(existing_raw)
        existing_sess = db.execute(
            select(AuthSession).where(
                AuthSession.token_hash == thash, AuthSession.kind == "guest"
            )
        ).scalar_one_or_none()
        if (
            existing_sess is not None
            and existing_sess.revoked_at is None
            and existing_sess.expires_at > now
        ):
            csrf_token = derive_csrf_token(
                existing_raw, "guest", str(existing_sess.id), settings.session_secret
            )
            db.rollback()
            return None, {
                "data": {
                    "guest_id": str(existing_sess.id),
                    "csrf_token": csrf_token,
                    "expires_at": iso_utc(existing_sess.expires_at),
                    "table": {
                        "id": str(table.id),
                        "number": table.number,
                        "label": table.label,
                    },
                    "current_bill_id": str(current_bill_id) if current_bill_id else None,
                }
            }

    guest_id = uuid.uuid4()
    raw_token = generate_opaque_token()
    token_hash = sha256_bytes(raw_token)
    csrf_token = derive_csrf_token(raw_token, "guest", str(guest_id), settings.session_secret)
    csrf_hash = sha256_bytes(csrf_token)
    expires_at = now + timedelta(seconds=GUEST_TTL_SECONDS)

    db.add(
        AuthSession(
            id=guest_id,
            token_hash=token_hash,
            kind="guest",
            staff_user_id=None,
            csrf_hash=csrf_hash,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
        )
    )
    commit_or_translate(db)
    return raw_token, {
        "data": {
            "guest_id": str(guest_id),
            "csrf_token": csrf_token,
            "expires_at": iso_utc(expires_at),
            "table": {
                "id": str(table.id),
                "number": table.number,
                "label": table.label,
            },
            "current_bill_id": str(current_bill_id) if current_bill_id else None,
        }
    }


def join_table_visit(
    request: Request, db: Session, guest: GuestPrincipal, payload: JoinInput
) -> dict[str, Any]:
    """Lock table, verify expected_bill_id matches current open bill, and grant membership."""
    ip = get_client_ip(request)
    rate_limiter.check(f"guest_bootstrap:{ip}", limit=30, window_seconds=60.0)

    table = resolve_enabled_table_by_qr(db, payload.qr_token, for_update=True)
    current_bill = db.execute(
        select(Bill)
        .where(Bill.table_id == table.id, Bill.status == "open")
        .with_for_update()
    ).scalar_one_or_none()

    current_open_id = current_bill.id if current_bill is not None else None
    if payload.expected_bill_id != current_open_id:
        db.rollback()
        raise AppError(
            status_code=409,
            code="TABLE_VISIT_CHANGED",
            message="Phiên bàn đã thay đổi. Vui lòng xác nhận tham gia lượt phục vụ hiện tại.",
            details={"current_bill_id": str(current_open_id) if current_open_id else None},
        )

    if current_bill is None:
        db.rollback()
        return {"data": {"bill_id": None, "membership": False}}

    now = utc_now()
    inserted = db.execute(
        text(
            """
            INSERT INTO bill_memberships (bill_id, guest_session_id, joined_at)
            VALUES (:bill_id, :guest_id, :joined_at)
            ON CONFLICT (bill_id, guest_session_id) DO NOTHING
            RETURNING bill_id
            """
        ),
        {
            "bill_id": current_bill.id,
            "guest_id": guest.session_id,
            "joined_at": now,
        },
    ).scalar_one_or_none()

    if inserted is not None:
        append_audit_event(
            db,
            request_id=get_request_id(request),
            principal_kind="guest",
            principal_id=guest.session_id,
            action="bill.join",
            resource_type="bill",
            resource_id=current_bill.id,
            before_state=None,
            after_state={"bill_id": str(current_bill.id)},
        )
    commit_or_translate(db)
    return {"data": {"bill_id": str(current_bill.id), "membership": True}}


def serialize_guest_menu_item(item: MenuItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "category_id": str(item.category_id),
        "name": item.name,
        "description": item.description,
        "price_vnd": format_money_vnd(item.price_vnd),
        "available": item.available,
        "version": item.version,
        "sort_order": item.sort_order,
    }


def serialize_kitchen_menu_item(item: MenuItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "category_id": str(item.category_id),
        "name": item.name,
        "available": item.available,
        "version": item.version,
        "sort_order": item.sort_order,
    }


def get_guest_menu_snapshot(
    db: Session, *, category_id: uuid.UUID | None = None
) -> dict[str, Any]:
    with repeatable_read_snapshot(db) as snap:
        cursor = str(read_event_watermark(snap))
        if category_id is not None:
            cat_exists = snap.execute(
                select(MenuCategory.id).where(MenuCategory.id == category_id)
            ).scalar_one_or_none()
            if cat_exists is None:
                raise AppError(
                    status_code=404,
                    code="NOT_FOUND",
                    message="Không tìm thấy danh mục thực đơn.",
                    details={},
                )

        categories = snap.execute(
            select(MenuCategory).order_by(MenuCategory.sort_order.asc(), MenuCategory.id.asc())
        ).scalars().all()

        item_stmt = select(MenuItem).where(MenuItem.active.is_(True))
        if category_id is not None:
            item_stmt = item_stmt.where(MenuItem.category_id == category_id)
        item_stmt = item_stmt.order_by(
            MenuItem.category_id.asc(), MenuItem.sort_order.asc(), MenuItem.id.asc()
        )
        items = snap.execute(item_stmt).scalars().all()
        shift_open = is_any_shift_open(snap)

        return {
            "data": {
                "categories": [
                    {
                        "id": str(c.id),
                        "name": c.name,
                        "sort_order": c.sort_order,
                    }
                    for c in categories
                ],
                "items": [serialize_guest_menu_item(i) for i in items],
                "version": cursor,
                "event_cursor": cursor,
                "shift_open": shift_open,
            }
        }


def get_kitchen_menu_snapshot(db: Session) -> dict[str, Any]:
    with repeatable_read_snapshot(db) as snap:
        cursor = str(read_event_watermark(snap))
        items = snap.execute(
            select(MenuItem)
            .where(MenuItem.active.is_(True))
            .order_by(MenuItem.category_id.asc(), MenuItem.sort_order.asc(), MenuItem.id.asc())
        ).scalars().all()
        shift_open = is_any_shift_open(snap)
        return {
            "data": {
                "items": [serialize_kitchen_menu_item(i) for i in items],
                "event_cursor": cursor,
                "shift_open": shift_open,
            }
        }


def update_menu_availability(
    request: Request,
    db: Session,
    staff: StaffPrincipal,
    item_id: uuid.UUID,
    payload: AvailabilityInput,
    *,
    after_menu_lock_hook: Callable[[], None] | None = None,
) -> tuple[int, dict[str, Any], bool]:
    # Pre-check item exists and is active before idempotency replay
    exists = db.execute(
        select(MenuItem.id).where(MenuItem.id == item_id, MenuItem.active.is_(True))
    ).scalar_one_or_none()
    db.rollback()
    if exists is None:
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy món trong thực đơn hoạt động.",
            details={},
        )

    idem_key = parse_idempotency_key(request)
    operation = f"PATCH:/api/v1/kitchen/menu/{item_id}/availability"
    res_id, replay_status, replay_body = reserve_or_replay_idempotency(
        db,
        principal_kind="staff",
        principal_id=staff.session_id,
        operation=operation,
        key=idem_key,
        payload={
            "expected_version": payload.expected_version,
            "available": payload.available,
        },
    )
    if replay_status is not None and replay_body is not None:
        return replay_status, replay_body, True
    assert res_id is not None

    item = db.execute(
        select(MenuItem)
        .where(MenuItem.id == item_id, MenuItem.active.is_(True))
        .with_for_update()
    ).scalar_one_or_none()
    if item is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy món trong thực đơn hoạt động.",
            details={},
        )

    if after_menu_lock_hook is not None:
        after_menu_lock_hook()

    if item.version != payload.expected_version:
        db.rollback()
        raise AppError(
            status_code=409,
            code="VERSION_CONFLICT",
            message="Trạng thái món vừa được thay đổi từ màn hình khác.",
            details={"current_version": item.version},
        )

    # Explicit target == current and version matches -> 200 no-op (no version/audit/event bump)
    if item.available == payload.available:
        cursor = str(read_event_watermark(db))
        noop_body: dict[str, Any] = {
            "data": {
                "item": serialize_kitchen_menu_item(item),
                "event_cursor": cursor,
            }
        }
        complete_idempotency_reservation(
            db, reservation_id=res_id, response_status=200, response_json=noop_body
        )
        commit_or_translate(db)
        return 200, noop_body, False

    before_avail = item.available
    before_ver = item.version
    item.available = payload.available
    item.version += 1
    db.flush()

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="staff",
        principal_id=staff.session_id,
        action="menu.availability",
        resource_type="menu_item",
        resource_id=item.id,
        before_state={"available": before_avail, "version": before_ver},
        after_state={"available": item.available, "version": item.version},
    )

    events = [
        PendingDomainEvent(
            audience=aud,
            event_type="menu.updated",
            resource_type="menu_item",
            resource_id=item.id,
            aggregate_version=item.version,
            bill_id=None,
        )
        for aud in ("menu", "kitchen", "cashier")
    ]
    cursor = allocate_and_append_domain_events(db, events)
    response_body: dict[str, Any] = {
        "data": {
            "item": serialize_kitchen_menu_item(item),
            "event_cursor": cursor,
        }
    }
    complete_idempotency_reservation(
        db, reservation_id=res_id, response_status=200, response_json=response_body
    )
    commit_or_translate(db)
    return 200, response_body, False


def export_table_qr(
    request: Request, db: Session, staff: StaffPrincipal, table_id: uuid.UUID
) -> dict[str, Any]:
    table = db.execute(
        select(DiningTable).where(DiningTable.id == table_id, DiningTable.enabled.is_(True))
    ).scalar_one_or_none()
    if table is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy bàn hoạt động.",
            details={},
        )

    settings = get_settings()
    raw_token = decrypt_qr_token(
        table.qr_token_encrypted,
        settings.qr_encryption_key,
        settings.qr_encryption_backup_keys,
    )
    if not hmac.compare_digest(sha256_bytes(raw_token), table.qr_token_hash):
        db.rollback()
        raise AppError(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message="Đối soát băm token QR thất bại.",
            details={},
        )

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="staff",
        principal_id=staff.session_id,
        action="qr.export",
        resource_type="table",
        resource_id=table.id,
        before_state=None,
        after_state={"table_number": table.number},
    )
    commit_or_translate(db)

    url = f"{settings.public_base_url}/t/{raw_token}"
    return {
        "data": {
            "table_number": table.number,
            "url": url,
        }
    }

