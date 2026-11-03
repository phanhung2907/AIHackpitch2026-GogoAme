"""F05 & F07 — Barista FIFO queue/status progression and cashier tables/bills/cash payments."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import exists, select, tuple_
from sqlalchemy.orm import Session

from app.db.session import read_event_watermark, repeatable_read_snapshot
from app.domain import (
    calculate_open_bill_total_vnd,
    compute_bill_can_pay,
    count_unfinished_items,
    derive_table_status,
    format_money_vnd,
    validate_kitchen_transition,
)
from app.errors import AppError
from app.models import Bill, DiningTable, Order, OrderItem, Payment
from app.schemas import ItemStatusInput, PaymentInput
from app.security import StaffPrincipal, utc_now
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
    require_open_shift_shared,
    reserve_or_replay_idempotency,
)
from app.services.ordering_and_billing import _load_bill_orders_and_items, serialize_payment


def encode_queue_cursor(
    *,
    created_at: datetime,
    order_id: uuid.UUID,
    status_filter: str | None,
    table_id_filter: uuid.UUID | None,
) -> str:
    payload = {
        "created_at": iso_utc(created_at),
        "id": str(order_id),
        "status": status_filter,
        "table_id": str(table_id_filter) if table_id_filter else None,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_queue_cursor(
    cursor: str,
    *,
    status_filter: str | None,
    table_id_filter: uuid.UUID | None,
) -> tuple[datetime, uuid.UUID]:
    try:
        padding = "=" * ((4 - len(cursor) % 4) % 4)
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii") + padding.encode("ascii"))
        obj = json.loads(decoded.decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("Cursor must decode to JSON object")
        expected_Keys = {"created_at", "id", "status", "table_id"}
        if set(obj.keys()) != expected_Keys:
            raise ValueError("Cursor keys mismatch")
        if obj["status"] != status_filter:
            raise ValueError("Cursor status filter mismatch")
        expected_table_str = str(table_id_filter) if table_id_filter else None
        if obj["table_id"] != expected_table_str:
            raise ValueError("Cursor table_id filter mismatch")
        ts_str = obj["created_at"]
        if not isinstance(ts_str, str):
            raise ValueError("Invalid created_at")
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        oid = uuid.UUID(str(obj["id"]))
        return dt, oid
    except Exception as exc:
        raise AppError(
            status_code=422,
            code="INVALID_CURSOR",
            message="Cursor phân trang hàng đợi không hợp lệ hoặc không khớp bộ lọc.",
            details={},
        ) from exc


def serialize_kitchen_item(item: OrderItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "menu_item_id": str(item.menu_item_id),
        "name": item.name_snapshot,
        "quantity": item.quantity,
        "note": item.note,
        "status": item.status,
        "version": item.version,
        "started_at": iso_utc(item.started_at),
    }


def serialize_cashier_item(item: OrderItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "menu_item_id": str(item.menu_item_id),
        "name": item.name_snapshot,
        "unit_price_vnd": format_money_vnd(item.unit_price_vnd),
        "quantity": item.quantity,
        "note": item.note,
        "status": item.status,
        "version": item.version,
    }


def get_kitchen_queue_snapshot(
    db: Session,
    *,
    cursor: str | None = None,
    limit: int = 50,
    status_filter: str | None = None,
    table_id_filter: uuid.UUID | None = None,
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Tham số limit phải từ 1 đến 100.",
            details={"field": "limit"},
        )
    if status_filter is not None and status_filter not in {"waiting", "preparing"}:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Tham số status chỉ nhận waiting hoặc preparing.",
            details={"field": "status"},
        )

    seek_tuple: tuple[datetime, uuid.UUID] | None = None
    if cursor is not None:
        seek_tuple = decode_queue_cursor(
            cursor, status_filter=status_filter, table_id_filter=table_id_filter
        )

    active_statuses = [status_filter] if status_filter else ["waiting", "preparing"]

    with repeatable_read_snapshot(db) as snap:
        event_cursor = str(read_event_watermark(snap))
        shift_open = is_any_shift_open(snap)

        item_exists_clause = exists(
            select(1).where(
                OrderItem.order_id == Order.id,
                OrderItem.status.in_(active_statuses),
            )
        )

        stmt = (
            select(Order, Bill.id, DiningTable)
            .join(Bill, Order.bill_id == Bill.id)
            .join(DiningTable, Bill.table_id == DiningTable.id)
            .where(Bill.status == "open", item_exists_clause)
        )
        if table_id_filter is not None:
            stmt = stmt.where(Bill.table_id == table_id_filter)
        if seek_tuple is not None:
            seek_dt, seek_id = seek_tuple
            stmt = stmt.where(tuple_(Order.created_at, Order.id) > (seek_dt, seek_id))

        stmt = stmt.order_by(Order.created_at.asc(), Order.id.asc()).limit(limit + 1)
        rows = list(snap.execute(stmt).all())

        has_more = len(rows) > limit
        page_rows = rows[:limit]

        if not page_rows:
            return {
                "data": [],
                "meta": {"next_cursor": None, "limit": limit},
                "event_cursor": event_cursor,
                "shift_open": shift_open,
            }

        page_order_ids = [r[0].id for r in page_rows]
        items = list(
            snap.execute(
                select(OrderItem)
                .where(
                    OrderItem.order_id.in_(page_order_ids),
                    OrderItem.status.in_(active_statuses),
                )
                .order_by(OrderItem.id.asc())
            ).scalars().all()
        )
        items_by_order: dict[uuid.UUID, list[OrderItem]] = {oid: [] for oid in page_order_ids}
        for it in items:
            items_by_order[it.order_id].append(it)

        tickets: list[dict[str, Any]] = []
        for order_obj, bill_id, table_obj in page_rows:
            tickets.append(
                {
                    "id": str(order_obj.id),
                    "order_number": str(order_obj.order_number),
                    "created_at": iso_utc(order_obj.created_at),
                    "table": {
                        "id": str(table_obj.id),
                        "number": table_obj.number,
                        "label": table_obj.label,
                    },
                    "bill_id": str(bill_id),
                    "items": [
                        serialize_kitchen_item(it) for it in items_by_order[order_obj.id]
                    ],
                }
            )

        next_cursor: str | None = None
        if has_more:
            last_order = page_rows[-1][0]
            next_cursor = encode_queue_cursor(
                created_at=last_order.created_at,
                order_id=last_order.id,
                status_filter=status_filter,
                table_id_filter=table_id_filter,
            )

        return {
            "data": tickets,
            "meta": {"next_cursor": next_cursor, "limit": limit},
            "event_cursor": event_cursor,
            "shift_open": shift_open,
        }


def update_kitchen_item_status(
    request: Request,
    db: Session,
    staff: StaffPrincipal,
    item_id: uuid.UUID,
    payload: ItemStatusInput,
    *,
    after_item_lock_hook: Callable[[], None] | None = None,
) -> tuple[int, dict[str, Any], bool]:
    # Pre-check item exists before idempotency replay
    preview = db.execute(
        select(OrderItem.id, Order.bill_id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.id == item_id)
    ).first()
    db.rollback()
    if preview is None:
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy dòng món cần cập nhật.",
            details={},
        )
    _, bill_id = preview

    idem_key = parse_idempotency_key(request)
    operation = f"PATCH:/api/v1/kitchen/items/{item_id}/status"
    res_id, replay_status, replay_body = reserve_or_replay_idempotency(
        db,
        principal_kind="staff",
        principal_id=staff.session_id,
        operation=operation,
        key=idem_key,
        payload={
            "expected_version": payload.expected_version,
            "status": payload.status,
        },
    )
    if replay_status is not None and replay_body is not None:
        return replay_status, replay_body, True
    assert res_id is not None

    # Lock order: bill FOR UPDATE -> order_item FOR UPDATE
    bill = db.execute(
        select(Bill).where(Bill.id == bill_id).with_for_update()
    ).scalar_one_or_none()
    if bill is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy hóa đơn của dòng món.",
            details={},
        )

    item = db.execute(
        select(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.id == item_id, Order.bill_id == bill.id)
        .with_for_update(of=OrderItem)
    ).scalar_one_or_none()
    if item is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy dòng món.",
            details={},
        )

    if after_item_lock_hook is not None:
        after_item_lock_hook()

    if bill.status != "open":
        db.rollback()
        raise AppError(
            status_code=409,
            code="BILL_CLOSED",
            message="Hóa đơn đã thanh toán, không thể đổi trạng thái pha chế.",
            details={"bill_id": str(bill.id), "status": bill.status},
        )

    # Check expected_version before state transition per api-design.md section 5
    if item.version != payload.expected_version:
        db.rollback()
        raise AppError(
            status_code=409,
            code="VERSION_CONFLICT",
            message="Dòng món đã được cập nhật bởi thao tác khác.",
            details={"current_version": item.version, "current_status": item.status},
        )

    try:
        validate_kitchen_transition(item.status, payload.status)
    except AppError:
        db.rollback()
        raise

    now = utc_now()
    before_status = item.status
    before_ver = item.version
    item.status = payload.status
    if payload.status == "preparing":
        item.started_at = now
    elif payload.status == "done":
        base_start = item.started_at or now
        item.done_at = max(now, base_start)
    item.version += 1
    bill.version += 1
    db.flush()

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="staff",
        principal_id=staff.session_id,
        action="item.progress",
        resource_type="order_item",
        resource_id=item.id,
        before_state={"status": before_status, "version": before_ver},
        after_state={
            "status": item.status,
            "version": item.version,
            "bill_version": bill.version,
        },
    )

    events = [
        PendingDomainEvent(
            audience=aud,
            event_type="item.updated",
            resource_type="order_item",
            resource_id=item.id,
            aggregate_version=item.version,
            bill_id=bill.id,
        )
        for aud in ("guest", "kitchen", "cashier")
    ] + [
        PendingDomainEvent(
            audience=aud,
            event_type="bill.updated",
            resource_type="bill",
            resource_id=bill.id,
            aggregate_version=bill.version,
            bill_id=bill.id,
        )
        for aud in ("guest", "cashier")
    ]
    cursor = allocate_and_append_domain_events(db, events)

    response_body: dict[str, Any] = {
        "data": {
            "item": serialize_kitchen_item(item),
            "event_cursor": cursor,
        }
    }
    complete_idempotency_reservation(
        db, reservation_id=res_id, response_status=200, response_json=response_body
    )
    commit_or_translate(db)
    return 200, response_body, False


def get_cashier_tables_snapshot(db: Session) -> dict[str, Any]:
    with repeatable_read_snapshot(db) as snap:
        cursor = str(read_event_watermark(snap))
        shift_open = is_any_shift_open(snap)
        tables = list(
            snap.execute(
                select(DiningTable)
                .where(DiningTable.enabled.is_(True))
                .order_by(DiningTable.number.asc())
            ).scalars().all()
        )
        open_bills = list(
            snap.execute(select(Bill).where(Bill.status == "open")).scalars().all()
        )
        open_bill_by_table = {b.table_id: b for b in open_bills}

        result: list[dict[str, Any]] = []
        for t in tables:
            b = open_bill_by_table.get(t.id)
            if b is None:
                result.append(
                    {
                        "id": str(t.id),
                        "number": t.number,
                        "label": t.label,
                        "status": "free",
                        "bill_id": None,
                        "total_vnd": "0",
                        "version": None,
                        "can_pay": False,
                    }
                )
            else:
                orders, _, all_items = _load_bill_orders_and_items(snap, b.id)
                total_vnd = calculate_open_bill_total_vnd(
                    (it.unit_price_vnd, it.quantity, it.status) for it in all_items
                )
                can_pay = compute_bill_can_pay(
                    b.status, shift_open, bool(orders), (it.status for it in all_items)
                )
                derived_st = derive_table_status(True, can_pay)
                result.append(
                    {
                        "id": str(t.id),
                        "number": t.number,
                        "label": t.label,
                        "status": derived_st,
                        "bill_id": str(b.id),
                        "total_vnd": format_money_vnd(total_vnd),
                        "version": b.version,
                        "can_pay": can_pay,
                    }
                )

        limit = max(1, len(result))
        return {
            "data": result,
            "meta": {"next_cursor": None, "limit": limit},
            "event_cursor": cursor,
        }


def get_cashier_bill_snapshot(db: Session, bill_id: uuid.UUID) -> dict[str, Any]:
    with repeatable_read_snapshot(db) as snap:
        cursor = str(read_event_watermark(snap))
        row = snap.execute(
            select(Bill, DiningTable.number)
            .join(DiningTable, Bill.table_id == DiningTable.id)
            .where(Bill.id == bill_id)
        ).first()
        if row is None:
            raise AppError(
                status_code=404,
                code="NOT_FOUND",
                message="Không tìm thấy hóa đơn.",
                details={},
            )
        bill, table_number = row
        orders, by_order, all_items = _load_bill_orders_and_items(snap, bill.id)
        payment = snap.execute(
            select(Payment).where(Payment.bill_id == bill.id)
        ).scalar_one_or_none()
        shift_open = is_any_shift_open(snap)

        if bill.status == "paid" and bill.total_vnd is not None:
            total_vnd = bill.total_vnd
        else:
            total_vnd = calculate_open_bill_total_vnd(
                (it.unit_price_vnd, it.quantity, it.status) for it in all_items
            )
        can_pay = compute_bill_can_pay(
            bill.status, shift_open, bool(orders), (it.status for it in all_items)
        )

        return {
            "data": {
                "id": str(bill.id),
                "table_id": str(bill.table_id),
                "table_number": int(table_number),
                "status": bill.status,
                "version": bill.version,
                "opened_at": iso_utc(bill.opened_at),
                "paid_at": iso_utc(bill.paid_at),
                "total_vnd": format_money_vnd(total_vnd),
                "can_pay": can_pay,
                "orders": [
                    {
                        "id": str(o.id),
                        "order_number": str(o.order_number),
                        "created_at": iso_utc(o.created_at),
                        "items": [serialize_cashier_item(it) for it in by_order[o.id]],
                    }
                    for o in orders
                ],
                "payment": serialize_payment(payment) if payment is not None else None,
                "event_cursor": cursor,
            }
        }


def create_cash_payment(
    request: Request,
    db: Session,
    staff: StaffPrincipal,
    bill_id: uuid.UUID,
    payload: PaymentInput,
    *,
    after_bill_lock_hook: Callable[[], None] | None = None,
    before_commit_hook: Callable[[], None] | None = None,
) -> tuple[int, dict[str, Any], bool]:
    # Pre-check bill exists before idempotency replay
    preview = db.execute(
        select(Bill.id, Bill.table_id).where(Bill.id == bill_id)
    ).first()
    db.rollback()
    if preview is None:
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy hóa đơn cần thanh toán.",
            details={},
        )
    _, table_id = preview

    idem_key = parse_idempotency_key(request)
    operation = f"POST:/api/v1/cashier/bills/{bill_id}/payments"
    res_id, replay_status, replay_body = reserve_or_replay_idempotency(
        db,
        principal_kind="staff",
        principal_id=staff.session_id,
        operation=operation,
        key=idem_key,
        payload={
            "expected_bill_version": payload.expected_bill_version,
            "expected_total_vnd": payload.expected_total_vnd,
            "method": payload.method,
        },
    )
    if replay_status is not None and replay_body is not None:
        return replay_status, replay_body, True
    assert res_id is not None

    # Global lock order: shift_guard (SHARE) -> shift (SHARE) -> table (UPDATE) -> bill (UPDATE)
    shift = require_open_shift_shared(db)
    table = db.execute(
        select(DiningTable).where(DiningTable.id == table_id).with_for_update()
    ).scalar_one_or_none()
    if table is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy bàn của hóa đơn.",
            details={},
        )

    bill = db.execute(
        select(Bill).where(Bill.id == bill_id).with_for_update()
    ).scalar_one_or_none()
    if bill is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy hóa đơn.",
            details={},
        )

    if after_bill_lock_hook is not None:
        after_bill_lock_hook()

    # Error precedence: closed -> shift match -> version -> unfinished -> amount
    if bill.status != "open":
        db.rollback()
        raise AppError(
            status_code=409,
            code="BILL_CLOSED",
            message="Hóa đơn này đã được thanh toán.",
            details={"bill_id": str(bill.id), "status": bill.status},
        )

    if bill.shift_id != shift.id:
        db.rollback()
        raise AppError(
            status_code=409,
            code="SHIFT_CLOSED",
            message="Ca của hóa đơn không khớp ca đang mở hiện tại.",
            details={"bill_shift_id": str(bill.shift_id), "current_shift_id": str(shift.id)},
        )

    if bill.version != payload.expected_bill_version:
        db.rollback()
        raise AppError(
            status_code=409,
            code="VERSION_CONFLICT",
            message="Hóa đơn vừa có cập nhật mới. Vui lòng kiểm tra lại trước khi thu tiền.",
            details={"current_version": bill.version},
        )

    orders, _, all_items = _load_bill_orders_and_items(db, bill.id)
    unfinished = count_unfinished_items(it.status for it in all_items)
    if not orders or unfinished > 0:
        db.rollback()
        raise AppError(
            status_code=409,
            code="ITEMS_NOT_DONE",
            message="Chưa thể thanh toán khi vẫn còn món đang chờ hoặc đang pha.",
            details={"unfinished_count": unfinished},
        )

    actual_total_vnd = calculate_open_bill_total_vnd(
        (it.unit_price_vnd, it.quantity, it.status) for it in all_items
    )
    expected_total_vnd = int(payload.expected_total_vnd)
    if expected_total_vnd != actual_total_vnd:
        db.rollback()
        raise AppError(
            status_code=409,
            code="AMOUNT_CHANGED",
            message="Tổng tiền hóa đơn đã thay đổi. Vui lòng đối chiếu lại.",
            details={"current_total_vnd": format_money_vnd(actual_total_vnd)},
        )

    paid_ts = max(utc_now(), bill.opened_at)
    before_ver = bill.version
    payment = Payment(
        id=uuid.uuid4(),
        bill_id=bill.id,
        shift_id=bill.shift_id,
        cashier_id=staff.user_id,
        method="cash",
        amount_vnd=actual_total_vnd,
        paid_at=paid_ts,
    )
    db.add(payment)

    bill.status = "paid"
    bill.paid_at = paid_ts
    bill.total_vnd = actual_total_vnd
    bill.version += 1
    db.flush()

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="staff",
        principal_id=staff.session_id,
        action="bill.pay",
        resource_type="bill",
        resource_id=bill.id,
        before_state={"status": "open", "version": before_ver},
        after_state={
            "status": "paid",
            "version": bill.version,
            "payment_id": str(payment.id),
            "amount_vnd": format_money_vnd(actual_total_vnd),
        },
    )

    events = [
        PendingDomainEvent(
            audience=aud,
            event_type="bill.closed",
            resource_type="bill",
            resource_id=bill.id,
            aggregate_version=bill.version,
            bill_id=bill.id,
        )
        for aud in ("guest", "kitchen", "cashier")
    ]
    cursor = allocate_and_append_domain_events(db, events)

    response_body: dict[str, Any] = {
        "data": {
            "payment": serialize_payment(payment),
            "bill": {
                "id": str(bill.id),
                "status": "paid",
                "version": bill.version,
                "total_vnd": format_money_vnd(actual_total_vnd),
            },
            "table": {
                "number": table.number,
                "status": "free",
            },
            "event_cursor": cursor,
        }
    }
    complete_idempotency_reservation(
        db, reservation_id=res_id, response_status=201, response_json=response_body
    )
    commit_or_translate(db, before_commit_hook=before_commit_hook)
    return 201, response_body, False

