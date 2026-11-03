"""F09, F11, F12 — Commit-ordered durable SSE streams, time/bestseller recommendations, and shift reports."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_session_factory, read_event_watermark, repeatable_read_snapshot
from app.domain import format_money_vnd, recommendation_bucket_for_utc
from app.errors import AppError
from app.models import (
    AuthSession,
    Bill,
    BillMembership,
    DomainEvent,
    EventClock,
    MenuCategory,
    MenuItem,
    Order,
    OrderItem,
    Payment,
    Shift,
    StaffUser,
)
from app.security import rate_limiter, sha256_bytes, utc_now
from app.services.common import commit_or_translate, iso_utc
from app.services.shifts import serialize_shift
from app.services.tables_and_menu import serialize_guest_menu_item

_CURSOR_RE = re.compile(r"^(0|[1-9][0-9]*)$")


def parse_sse_cursor(after_query: str | None, last_event_id_header: str | None) -> int:
    """Validate and parse SSE cursor (Last-Event-ID takes precedence over ?after=)."""
    if last_event_id_header is not None and last_event_id_header.strip() != "":
        candidate = last_event_id_header.strip()
        if not _CURSOR_RE.match(candidate):
            raise AppError(
                status_code=422,
                code="INVALID_CURSOR",
                message="Header Last-Event-ID không đúng định dạng số nguyên không âm.",
                details={"header": "Last-Event-ID"},
            )
        return int(candidate)

    if after_query is not None:
        candidate = after_query.strip()
        if not _CURSOR_RE.match(candidate):
            raise AppError(
                status_code=422,
                code="INVALID_CURSOR",
                message="Tham số after không đúng định dạng cursor hợp lệ.",
                details={"field": "after"},
            )
        return int(candidate)

    return 0


def format_sse_frame(
    *,
    event: str,
    data: dict[str, Any],
    event_id: str | None = None,
) -> str:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, separators=(',', ':'), ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


def prune_domain_events(db: Session, *, retain_after_id: int) -> None:
    """Atomically prune committed domain_events prefix and advance retained_after under event_clock lock."""
    clock = db.execute(
        select(EventClock).where(EventClock.id == 1).with_for_update()
    ).scalar_one()
    if retain_after_id < clock.retained_after or retain_after_id > clock.last_id:
        db.rollback()
        raise ValueError(
            f"retain_after_id ({retain_after_id}) must be between {clock.retained_after} and {clock.last_id}"
        )
    db.execute(
        text("DELETE FROM domain_events WHERE id <= :cutoff"),
        {"cutoff": retain_after_id},
    )
    clock.retained_after = retain_after_id
    commit_or_translate(db)


def _check_stream_principal_active(
    snap: Session,
    *,
    principal_kind: str,
    raw_cookie_token: str,
    required_role: str | None = None,
    bill_id: uuid.UUID | None = None,
) -> bool:
    now = utc_now()
    thash = sha256_bytes(raw_cookie_token)
    if principal_kind == "guest":
        sess = snap.execute(
            select(AuthSession).where(
                AuthSession.token_hash == thash, AuthSession.kind == "guest"
            )
        ).scalar_one_or_none()
        if sess is None or sess.revoked_at is not None or sess.expires_at <= now:
            return False
        if bill_id is not None:
            mem = snap.execute(
                select(BillMembership).where(
                    BillMembership.bill_id == bill_id,
                    BillMembership.guest_session_id == sess.id,
                )
            ).scalar_one_or_none()
            if mem is None:
                return False
        return True

    row = snap.execute(
        select(AuthSession, StaffUser)
        .join(StaffUser, AuthSession.staff_user_id == StaffUser.id)
        .where(AuthSession.token_hash == thash, AuthSession.kind == "staff")
    ).first()
    if row is None:
        return False
    sess, user = row
    if sess.revoked_at is not None or sess.expires_at <= now or not user.active:
        return False
    if required_role is not None and user.role != required_role:
        return False
    return True


def fetch_sse_batch_short_tx(
    *,
    principal_kind: str,
    raw_cookie_token: str,
    audience: str,
    cursor: int,
    required_role: str | None = None,
    bill_id: uuid.UUID | None = None,
) -> tuple[str, list[str], int]:
    """Execute a single short-lived REPEATABLE READ batch query and immediately close DB session.

    Returns (status, frames, next_cursor) where status is 'ok', 'expired', or 'reset'.
    """
    factory = get_session_factory()
    db = factory()
    try:
        with repeatable_read_snapshot(db) as snap:
            if not _check_stream_principal_active(
                snap,
                principal_kind=principal_kind,
                raw_cookie_token=raw_cookie_token,
                required_role=required_role,
                bill_id=bill_id,
            ):
                return (
                    "expired",
                    [format_sse_frame(event="session_expired", data={"reason": "session_expired"})],
                    cursor,
                )

            clock = snap.execute(select(EventClock).where(EventClock.id == 1)).scalar_one()
            high_watermark = int(clock.last_id)
            retained_after = int(clock.retained_after)

            if cursor < retained_after or cursor > high_watermark:
                return (
                    "reset",
                    [format_sse_frame(event="reset", data={"reason": "cursor_out_of_range"})],
                    cursor,
                )

            if cursor == high_watermark:
                return "ok", [], cursor

            stmt = select(DomainEvent).where(
                DomainEvent.audience == audience,
                DomainEvent.id > cursor,
                DomainEvent.id <= high_watermark,
            )
            if audience == "guest":
                stmt = stmt.where(DomainEvent.bill_id == bill_id)
            stmt = stmt.order_by(DomainEvent.id.asc()).limit(100)
            events = list(snap.execute(stmt).scalars().all())

            frames: list[str] = []
            for ev in events:
                ev_id_str = str(ev.id)
                frames.append(
                    format_sse_frame(
                        event=ev.event_type,
                        event_id=ev_id_str,
                        data={
                            "id": ev_id_str,
                            "type": ev.event_type,
                            "resource_id": str(ev.resource_id),
                            "version": ev.aggregate_version,
                            "occurred_at": iso_utc(ev.created_at),
                        },
                    )
                )

            if len(events) == 100:
                next_cursor = int(events[-1].id)
            else:
                next_cursor = high_watermark
                if not events and high_watermark > cursor:
                    frames.append(
                        format_sse_frame(
                            event="checkpoint",
                            event_id=str(high_watermark),
                            data={"cursor": str(high_watermark)},
                        )
                    )

            return "ok", frames, next_cursor
    finally:
        db.close()


async def sse_event_generator(
    request: Request,
    *,
    principal_key: str,
    principal_kind: str,
    raw_cookie_token: str,
    audience: str,
    initial_cursor: int,
    required_role: str | None = None,
    bill_id: uuid.UUID | None = None,
    max_ticks: int | None = None,
) -> AsyncGenerator[str, None]:
    """Stream SSE events without holding a DB connection across sleep/socket writes."""
    settings = get_settings()
    poll_interval = settings.sse_poll_interval_seconds
    heartbeat_interval = settings.sse_heartbeat_seconds

    with rate_limiter.acquire_sse_slot(principal_key):
        cursor = initial_cursor
        last_heartbeat = time.monotonic()
        ticks = 0

        # Initial heartbeat comment so headers/stream flush immediately
        yield ": connected\n\n"

        while True:
            if await request.is_disconnected():
                break

            status, frames, cursor = fetch_sse_batch_short_tx(
                principal_kind=principal_kind,
                raw_cookie_token=raw_cookie_token,
                audience=audience,
                cursor=cursor,
                required_role=required_role,
                bill_id=bill_id,
            )

            # Bounded backpressure: max 100 frames per batch; yield sequentially
            for frame in frames:
                yield frame

            if status in {"expired", "reset"}:
                break

            now_mono = time.monotonic()
            if now_mono - last_heartbeat >= heartbeat_interval:
                yield ": heartbeat\n\n"
                last_heartbeat = now_mono

            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break

            await asyncio.sleep(poll_interval)


# --- P2: F11 Guest Recommendations ---
def get_guest_recommendations_snapshot(
    db: Session,
    *,
    clock_fn: Callable[[], datetime] = utc_now,
) -> dict[str, Any]:
    settings = get_settings()
    now = clock_fn()
    target_bucket = recommendation_bucket_for_utc(now, settings.demo_timezone)
    window_start = now - timedelta(days=7)

    with repeatable_read_snapshot(db) as snap:
        cursor = str(read_event_watermark(snap))
        rows = list(
            snap.execute(
                select(MenuItem, MenuCategory.recommendation_bucket, MenuCategory.sort_order)
                .join(MenuCategory, MenuItem.category_id == MenuCategory.id)
                .where(MenuItem.active.is_(True), MenuItem.available.is_(True))
                .order_by(
                    MenuCategory.sort_order.asc(),
                    MenuItem.sort_order.asc(),
                    MenuItem.id.asc(),
                )
            ).all()
        )
        if not rows:
            return {"data": {"items": [], "event_cursor": cursor}}

        available_by_id: dict[uuid.UUID, MenuItem] = {r[0].id: r[0] for r in rows}
        selected: list[dict[str, Any]] = []
        picked_ids: set[uuid.UUID] = set()

        # 1. Time-of-day bucket candidates
        for item_obj, bucket, _ in rows:
            if bucket == target_bucket and item_obj.id not in picked_ids:
                picked_ids.add(item_obj.id)
                selected.append(
                    {
                        "item": serialize_guest_menu_item(item_obj),
                        "reason": "time_of_day",
                    }
                )
                if len(selected) >= 3:
                    return {"data": {"items": selected, "event_cursor": cursor}}

        # 2. Bestsellers in [now - 7 days, now] from paid bills & non-cancelled items
        bestseller_rows = list(
            snap.execute(
                select(
                    OrderItem.menu_item_id,
                    func.sum(OrderItem.quantity).label("sold_qty"),
                )
                .join(Order, OrderItem.order_id == Order.id)
                .join(Bill, Order.bill_id == Bill.id)
                .join(Payment, Payment.bill_id == Bill.id)
                .where(
                    Bill.status == "paid",
                    OrderItem.status != "cancelled",
                    Payment.paid_at >= window_start,
                    Payment.paid_at <= now,
                )
                .group_by(OrderItem.menu_item_id)
                .order_by(desc("sold_qty"), OrderItem.menu_item_id.asc())
            ).all()
        )
        for menu_item_id, _sold_qty in bestseller_rows:
            if menu_item_id in available_by_id and menu_item_id not in picked_ids:
                picked_ids.add(menu_item_id)
                selected.append(
                    {
                        "item": serialize_guest_menu_item(available_by_id[menu_item_id]),
                        "reason": "bestseller",
                    }
                )
                if len(selected) >= 3:
                    return {"data": {"items": selected, "event_cursor": cursor}}

        # 3. Seed order fallback
        for item_obj, _, _ in rows:
            if item_obj.id not in picked_ids:
                picked_ids.add(item_obj.id)
                selected.append(
                    {
                        "item": serialize_guest_menu_item(item_obj),
                        "reason": "seed_order",
                    }
                )
                if len(selected) >= 3:
                    break

        return {"data": {"items": selected, "event_cursor": cursor}}


# --- P2: F12 Cashier Shift Report ---
def get_shift_report_snapshot(
    db: Session,
    shift_id: uuid.UUID,
    *,
    clock_fn: Callable[[], datetime] = utc_now,
) -> dict[str, Any]:
    as_of = clock_fn()
    with repeatable_read_snapshot(db) as snap:
        cursor = str(read_event_watermark(snap))
        shift = snap.execute(select(Shift).where(Shift.id == shift_id)).scalar_one_or_none()
        if shift is None:
            raise AppError(
                status_code=404,
                code="NOT_FOUND",
                message="Không tìm thấy ca làm việc.",
                details={},
            )

        # Separate aggregate on payments so JOIN never multiplies revenue
        rev_row = snap.execute(
            select(
                func.coalesce(func.sum(Payment.amount_vnd), 0),
                func.count(Payment.id),
            ).where(Payment.shift_id == shift_id)
        ).one()
        revenue_vnd = int(rev_row[0])
        paid_bill_count = int(rev_row[1])

        # Separate top-5 items query across paid bills in this shift, excluding cancelled items
        top_rows = list(
            snap.execute(
                select(
                    OrderItem.menu_item_id,
                    func.sum(OrderItem.quantity).label("total_qty"),
                )
                .join(Order, OrderItem.order_id == Order.id)
                .join(Bill, Order.bill_id == Bill.id)
                .join(Payment, Payment.bill_id == Bill.id)
                .where(
                    Payment.shift_id == shift_id,
                    Bill.status == "paid",
                    OrderItem.status != "cancelled",
                )
                .group_by(OrderItem.menu_item_id)
                .order_by(desc("total_qty"), OrderItem.menu_item_id.asc())
                .limit(5)
            ).all()
        )

        top_items: list[dict[str, Any]] = []
        for menu_item_id, total_qty in top_rows:
            latest_name = snap.execute(
                select(OrderItem.name_snapshot)
                .join(Order, OrderItem.order_id == Order.id)
                .join(Bill, Order.bill_id == Bill.id)
                .join(Payment, Payment.bill_id == Bill.id)
                .where(
                    Payment.shift_id == shift_id,
                    Bill.status == "paid",
                    OrderItem.status != "cancelled",
                    OrderItem.menu_item_id == menu_item_id,
                )
                .order_by(Order.created_at.desc(), OrderItem.id.desc())
                .limit(1)
            ).scalar_one()
            top_items.append(
                {
                    "menu_item_id": str(menu_item_id),
                    "name": str(latest_name),
                    "quantity": int(total_qty),
                }
            )

        return {
            "data": {
                "shift": serialize_shift(shift),
                "revenue_vnd": format_money_vnd(revenue_vnd),
                "paid_bill_count": paid_bill_count,
                "top_items": top_items,
                "as_of": iso_utc(as_of),
                "event_cursor": cursor,
            }
        }

