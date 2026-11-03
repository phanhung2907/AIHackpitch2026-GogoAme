"""Common transaction, locking, idempotency, event clock, and audit helpers."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request
from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import translate_db_operational_error
from app.errors import AppError
from app.models import AuditEvent, DomainEvent, IdempotencyRecord, Shift, ShiftGuard
from app.security.crypto import compute_idempotency_hash


@dataclass(frozen=True)
class PendingDomainEvent:
    audience: str
    event_type: str
    resource_type: str
    resource_id: uuid.UUID
    aggregate_version: int
    bill_id: uuid.UUID | None = None


def iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def get_request_id(request: Request | None) -> str:
    if request is not None and hasattr(request.state, "request_id"):
        return str(request.state.request_id)
    return f"req-{uuid.uuid4().hex[:12]}"


def parse_idempotency_key(request: Request) -> uuid.UUID:
    raw = request.headers.get("Idempotency-Key")
    if not raw:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Thiếu header Idempotency-Key (UUID).",
            details={"header": "Idempotency-Key"},
        )
    try:
        return uuid.UUID(raw.strip())
    except ValueError as exc:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Header Idempotency-Key phải đúng định dạng UUID.",
            details={"header": "Idempotency-Key"},
        ) from exc


def reserve_or_replay_idempotency(
    db: Session,
    *,
    principal_kind: str,
    principal_id: uuid.UUID,
    operation: str,
    key: uuid.UUID,
    payload: dict[str, Any],
) -> tuple[uuid.UUID | None, int | None, dict[str, Any] | None]:
    """Reserve idempotency record in current transaction or return committed replay.

    Returns (reservation_id, replay_status, replay_json).
    If replay_status is not None, the caller must return the replayed response immediately.
    """
    payload_hash = compute_idempotency_hash(operation, payload)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    for _ in range(2):
        rec_id = uuid.uuid4()
        inserted_id = db.execute(
            text(
                """
                INSERT INTO idempotency_records
                    (id, principal_kind, principal_id, operation, key, payload_hash, created_at, expires_at)
                VALUES
                    (:id, :pk, :pid, :op, :key, :phash, :created_at, :expires_at)
                ON CONFLICT (principal_kind, principal_id, operation, key) DO NOTHING
                RETURNING id
                """
            ),
            {
                "id": rec_id,
                "pk": principal_kind,
                "pid": principal_id,
                "op": operation,
                "key": key,
                "phash": payload_hash,
                "created_at": now,
                "expires_at": expires_at,
            },
        ).scalar_one_or_none()

        if inserted_id is not None:
            return uuid.UUID(str(inserted_id)), None, None

        existing = db.execute(
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.principal_kind == principal_kind,
                IdempotencyRecord.principal_id == principal_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key == key,
            )
            .with_for_update()
        ).scalar_one_or_none()

        if existing is None:
            continue

        if not hmac.compare_digest(existing.payload_hash, payload_hash):
            db.rollback()
            raise AppError(
                status_code=409,
                code="IDEMPOTENCY_CONFLICT",
                message="Idempotency-Key đã được dùng cho một nội dung lệnh khác.",
                details={},
            )

        assert existing.response_status is not None and existing.response_json is not None
        status = int(existing.response_status)
        body = dict(existing.response_json)
        db.rollback()
        return None, status, body

    raise AppError(
        status_code=503,
        code="RETRYABLE_CONFLICT",
        message="Không thể khóa bản ghi idempotency, vui lòng thử lại.",
        details={},
    )


def complete_idempotency_reservation(
    db: Session,
    *,
    reservation_id: uuid.UUID,
    response_status: int,
    response_json: dict[str, Any],
) -> None:
    db.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.id == reservation_id)
        .values(response_status=response_status, response_json=response_json)
    )


def lock_shift_guard(db: Session, *, exclusive: bool) -> ShiftGuard:
    stmt = select(ShiftGuard).where(ShiftGuard.id == 1)
    if exclusive:
        stmt = stmt.with_for_update()
    else:
        stmt = stmt.with_for_update(read=True)
    guard = db.execute(stmt).scalar_one()
    return guard


def require_open_shift_shared(db: Session) -> Shift:
    """Acquire shared lock on shift_guard and current open shift; raise 409 SHIFT_CLOSED if none."""
    lock_shift_guard(db, exclusive=False)
    shift = db.execute(
        select(Shift).where(Shift.status == "open").with_for_update(read=True)
    ).scalar_one_or_none()
    if shift is None:
        raise AppError(
            status_code=409,
            code="SHIFT_CLOSED",
            message="Quán hiện chưa mở ca phục vụ.",
            details={},
        )
    return shift


def is_any_shift_open(db: Session) -> bool:
    row = db.execute(select(Shift.id).where(Shift.status == "open").limit(1)).scalar_one_or_none()
    return row is not None


def append_audit_event(
    db: Session,
    *,
    request_id: str,
    principal_kind: str,
    principal_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    before_state: dict[str, Any] | None,
    after_state: dict[str, Any] | None,
) -> None:
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            request_id=request_id,
            principal_kind=principal_kind,
            principal_id=principal_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
        )
    )


def allocate_and_append_domain_events(
    db: Session,
    events: Sequence[PendingDomainEvent],
    *,
    after_clock_lock_hook: Callable[[], None] | None = None,
) -> str:
    """Lock singleton event_clock FOR UPDATE at the end of transaction and append domain events."""
    current_last_id = int(
        db.execute(text("SELECT last_id FROM event_clock WHERE id = 1 FOR UPDATE")).scalar_one()
    )
    if not events:
        return str(current_last_id)

    now = datetime.now(timezone.utc)
    next_id = current_last_id
    for ev in events:
        next_id += 1
        db.add(
            DomainEvent(
                id=next_id,
                bill_id=ev.bill_id,
                audience=ev.audience,
                event_type=ev.event_type,
                resource_type=ev.resource_type,
                resource_id=ev.resource_id,
                aggregate_version=ev.aggregate_version,
                created_at=now,
            )
        )
    db.execute(
        text("UPDATE event_clock SET last_id = :new_last_id WHERE id = 1"),
        {"new_last_id": next_id},
    )
    db.flush()
    if after_clock_lock_hook is not None:
        after_clock_lock_hook()
    return str(next_id)


def commit_or_translate(
    db: Session,
    *,
    before_commit_hook: Callable[[], None] | None = None,
) -> None:
    try:
        if before_commit_hook is not None:
            before_commit_hook()
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise translate_db_operational_error(exc) from exc
    except Exception:
        db.rollback()
        raise

