"""F08 — Shift management (current shift snapshot, open shift, close shift with open-bill guard)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import read_event_watermark, repeatable_read_snapshot
from app.errors import AppError
from app.models import Bill, Shift
from app.schemas import CloseShiftInput
from app.security import StaffPrincipal, utc_now
from app.services.common import (
    PendingDomainEvent,
    allocate_and_append_domain_events,
    append_audit_event,
    commit_or_translate,
    complete_idempotency_reservation,
    get_request_id,
    iso_utc,
    lock_shift_guard,
    parse_idempotency_key,
    reserve_or_replay_idempotency,
)


def serialize_shift(shift: Shift) -> dict[str, Any]:
    return {
        "id": str(shift.id),
        "status": shift.status,
        "opened_at": iso_utc(shift.opened_at),
        "closed_at": iso_utc(shift.closed_at),
        "version": shift.version,
    }


def get_current_shift_snapshot(db: Session) -> dict[str, Any]:
    with repeatable_read_snapshot(db) as snap:
        cursor = str(read_event_watermark(snap))
        current = snap.execute(
            select(Shift).where(Shift.status == "open")
        ).scalar_one_or_none()
        return {
            "data": {
                "shift": serialize_shift(current) if current is not None else None,
                "event_cursor": cursor,
            }
        }


def open_shift(
    request: Request,
    db: Session,
    staff: StaffPrincipal,
    *,
    after_guard_lock_hook: Callable[[], None] | None = None,
) -> tuple[int, dict[str, Any], bool]:
    idem_key = parse_idempotency_key(request)
    operation = "POST:/api/v1/cashier/shifts"
    res_id, replay_status, replay_body = reserve_or_replay_idempotency(
        db,
        principal_kind="staff",
        principal_id=staff.session_id,
        operation=operation,
        key=idem_key,
        payload={},
    )
    if replay_status is not None and replay_body is not None:
        return replay_status, replay_body, True
    assert res_id is not None

    guard = lock_shift_guard(db, exclusive=True)
    if after_guard_lock_hook is not None:
        after_guard_lock_hook()

    existing_open = db.execute(
        select(Shift).where(Shift.status == "open")
    ).scalar_one_or_none()
    if existing_open is not None:
        db.rollback()
        raise AppError(
            status_code=409,
            code="SHIFT_ALREADY_OPEN",
            message="Đã có một ca đang mở.",
            details={"shift_id": str(existing_open.id)},
        )

    now = utc_now()
    new_shift = Shift(
        id=uuid.uuid4(),
        status="open",
        opened_by=staff.user_id,
        opened_at=now,
        closed_by=None,
        closed_at=None,
        version=1,
    )
    db.add(new_shift)
    guard.version += 1
    db.flush()

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="staff",
        principal_id=staff.session_id,
        action="shift.open",
        resource_type="shift",
        resource_id=new_shift.id,
        before_state=None,
        after_state={"status": "open", "version": 1},
    )

    events = [
        PendingDomainEvent(
            audience=aud,
            event_type="shift.updated",
            resource_type="shift",
            resource_id=new_shift.id,
            aggregate_version=new_shift.version,
            bill_id=None,
        )
        for aud in ("menu", "kitchen", "cashier")
    ]
    cursor = allocate_and_append_domain_events(db, events)
    response_body: dict[str, Any] = {
        "data": {
            "shift": serialize_shift(new_shift),
            "event_cursor": cursor,
        }
    }
    complete_idempotency_reservation(
        db, reservation_id=res_id, response_status=201, response_json=response_body
    )
    commit_or_translate(db)
    return 201, response_body, False


def close_shift(
    request: Request,
    db: Session,
    staff: StaffPrincipal,
    shift_id: uuid.UUID,
    payload: CloseShiftInput,
    *,
    after_guard_lock_hook: Callable[[], None] | None = None,
) -> tuple[int, dict[str, Any], bool]:
    # Pre-check resource existence before idempotency replay
    exists = db.execute(select(Shift.id).where(Shift.id == shift_id)).scalar_one_or_none()
    db.rollback()
    if exists is None:
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy ca làm việc.",
            details={},
        )

    idem_key = parse_idempotency_key(request)
    operation = f"POST:/api/v1/cashier/shifts/{shift_id}/close"
    res_id, replay_status, replay_body = reserve_or_replay_idempotency(
        db,
        principal_kind="staff",
        principal_id=staff.session_id,
        operation=operation,
        key=idem_key,
        payload={"expected_version": payload.expected_version},
    )
    if replay_status is not None and replay_body is not None:
        return replay_status, replay_body, True
    assert res_id is not None

    guard = lock_shift_guard(db, exclusive=True)
    if after_guard_lock_hook is not None:
        after_guard_lock_hook()

    shift = db.execute(
        select(Shift).where(Shift.id == shift_id).with_for_update()
    ).scalar_one_or_none()
    if shift is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy ca làm việc.",
            details={},
        )

    if shift.status != "open":
        db.rollback()
        raise AppError(
            status_code=409,
            code="STATE_CONFLICT",
            message="Ca làm việc này đã được đóng trước đó.",
            details={"current_status": shift.status},
        )

    if shift.version != payload.expected_version:
        db.rollback()
        raise AppError(
            status_code=409,
            code="VERSION_CONFLICT",
            message="Dữ liệu ca làm việc đã thay đổi.",
            details={"current_version": shift.version},
        )

    open_bill_count = int(
        db.execute(
            select(func.count(Bill.id)).where(Bill.status == "open")
        ).scalar_one()
    )
    if open_bill_count > 0:
        db.rollback()
        raise AppError(
            status_code=409,
            code="OPEN_BILLS_EXIST",
            message="Không thể đóng ca khi vẫn còn hóa đơn đang mở.",
            details={"open_bill_count": open_bill_count},
        )

    now = utc_now()
    before_ver = shift.version
    shift.status = "closed"
    shift.closed_by = staff.user_id
    shift.closed_at = max(now, shift.opened_at)
    shift.version += 1
    guard.version += 1
    db.flush()

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="staff",
        principal_id=staff.session_id,
        action="shift.close",
        resource_type="shift",
        resource_id=shift.id,
        before_state={"status": "open", "version": before_ver},
        after_state={"status": "closed", "version": shift.version},
    )

    events = [
        PendingDomainEvent(
            audience=aud,
            event_type="shift.updated",
            resource_type="shift",
            resource_id=shift.id,
            aggregate_version=shift.version,
            bill_id=None,
        )
        for aud in ("menu", "kitchen", "cashier")
    ]
    cursor = allocate_and_append_domain_events(db, events)
    response_body: dict[str, Any] = {
        "data": {
            "shift": serialize_shift(shift),
            "event_cursor": cursor,
        }
    }
    complete_idempotency_reservation(
        db, reservation_id=res_id, response_status=200, response_json=response_body
    )
    commit_or_translate(db)
    return 200, response_body, False

