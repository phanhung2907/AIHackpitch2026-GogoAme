"""F03 & F04 — Guest order submission, add-on orders, bill snapshot, and waiting item cancellation."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import read_event_watermark, repeatable_read_snapshot
from app.domain import (
    calculate_line_total_vnd,
    calculate_open_bill_total_vnd,
    can_guest_cancel_item,
    compute_bill_can_pay,
    format_money_vnd,
    validate_guest_cancel_state,
    validate_order_lines_limits,
)
from app.errors import AppError
from app.models import (
    Bill,
    BillMembership,
    DiningTable,
    MenuItem,
    Order,
    OrderItem,
    Payment,
)
from app.schemas import ItemVersionInput, OrderInput
from app.security import GuestPrincipal, utc_now
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
from app.services.tables_and_menu import resolve_enabled_table_by_qr


def _sequential_uuid4s(count: int) -> list[uuid.UUID]:
    """Generate monotonically increasing valid UUIDv4 values so ID sort preserves input order."""
    # 96 random high bits + 26-bit counter in low bits, with RFC 4122 v4 variant/version bits
    high_rand = secrets.randbits(96) << 32
    result: list[uuid.UUID] = []
    for idx in range(count):
        raw_128 = high_rand | (idx + 1)
        # Set version=4 (bits 76..79) and variant=0b10 (bits 62..63)
        raw_128 &= ~(0xF << 76)
        raw_128 |= 0x4 << 76
        raw_128 &= ~(0x3 << 62)
        raw_128 |= 0x2 << 62
        result.append(uuid.UUID(int=raw_128))
    return result


def serialize_guest_item(
    item: OrderItem, *, creator_session_id: uuid.UUID, viewer_session_id: uuid.UUID, bill_status: str
) -> dict[str, Any]:
    is_mine = creator_session_id == viewer_session_id
    return {
        "id": str(item.id),
        "menu_item_id": str(item.menu_item_id),
        "name": item.name_snapshot,
        "unit_price_vnd": format_money_vnd(item.unit_price_vnd),
        "quantity": item.quantity,
        "note": item.note,
        "status": item.status,
        "version": item.version,
        "is_mine": is_mine,
        "can_cancel": can_guest_cancel_item(is_mine, bill_status, item.status),
    }


def serialize_payment(payment: Payment) -> dict[str, Any]:
    return {
        "id": str(payment.id),
        "bill_id": str(payment.bill_id),
        "shift_id": str(payment.shift_id),
        "amount_vnd": format_money_vnd(payment.amount_vnd),
        "method": payment.method,
        "paid_at": iso_utc(payment.paid_at),
    }


def _load_bill_orders_and_items(
    db: Session, bill_id: uuid.UUID
) -> tuple[list[Order], dict[uuid.UUID, list[OrderItem]], list[OrderItem]]:
    orders = list(
        db.execute(
            select(Order)
            .where(Order.bill_id == bill_id)
            .order_by(Order.created_at.asc(), Order.id.asc())
        ).scalars().all()
    )
    if not orders:
        return [], {}, []
    order_ids = [o.id for o in orders]
    all_items = list(
        db.execute(
            select(OrderItem)
            .where(OrderItem.order_id.in_(order_ids))
            .order_by(OrderItem.id.asc())
        ).scalars().all()
    )
    by_order: dict[uuid.UUID, list[OrderItem]] = {o.id: [] for o in orders}
    for it in all_items:
        by_order[it.order_id].append(it)
    return orders, by_order, all_items


def submit_order(
    request: Request,
    db: Session,
    guest: GuestPrincipal,
    payload: OrderInput,
    *,
    after_table_lock_hook: Callable[[], None] | None = None,
    after_menu_lock_hook: Callable[[], None] | None = None,
    before_commit_hook: Callable[[], None] | None = None,
    after_clock_lock_hook: Callable[[], None] | None = None,
) -> tuple[int, dict[str, Any], bool]:
    # Step 1: Pre-check QR table and membership scope before idempotency replay
    table_preview = resolve_enabled_table_by_qr(db, payload.qr_token, for_update=False)
    if payload.expected_bill_id is not None:
        bill_preview = db.execute(
            select(Bill).where(
                Bill.id == payload.expected_bill_id,
                Bill.table_id == table_preview.id,
            )
        ).scalar_one_or_none()
        membership_preview = db.execute(
            select(BillMembership).where(
                BillMembership.bill_id == payload.expected_bill_id,
                BillMembership.guest_session_id == guest.session_id,
            )
        ).scalar_one_or_none()
        if bill_preview is None or membership_preview is None:
            db.rollback()
            raise AppError(
                status_code=404,
                code="NOT_FOUND",
                message="Không tìm thấy hóa đơn thuộc phiên khách hiện tại.",
                details={},
            )
    db.rollback()

    # Step 2: Idempotency reservation / replay
    idem_key = parse_idempotency_key(request)
    operation = f"POST:/api/v1/guest/orders:{table_preview.id}"
    canonical_payload = {
        "qr_token": payload.qr_token,
        "expected_bill_id": str(payload.expected_bill_id) if payload.expected_bill_id else None,
        "items": [
            {
                "menu_item_id": str(line.menu_item_id),
                "quantity": line.quantity,
                "note": line.note,
                "expected_unit_price_vnd": line.expected_unit_price_vnd,
            }
            for line in payload.items
        ],
    }
    res_id, replay_status, replay_body = reserve_or_replay_idempotency(
        db,
        principal_kind="guest",
        principal_id=guest.session_id,
        operation=operation,
        key=idem_key,
        payload=canonical_payload,
    )
    if replay_status is not None and replay_body is not None:
        return replay_status, replay_body, True
    assert res_id is not None

    # Step 3: Global lock order: shift_guard (SHARE) -> shift (SHARE) -> table (UPDATE) -> bill (UPDATE)
    shift = require_open_shift_shared(db)
    table = resolve_enabled_table_by_qr(db, payload.qr_token, for_update=True)
    if after_table_lock_hook is not None:
        after_table_lock_hook()

    if payload.expected_bill_id is not None:
        expected_bill = db.execute(
            select(Bill)
            .where(Bill.id == payload.expected_bill_id, Bill.table_id == table.id)
            .with_for_update()
        ).scalar_one_or_none()
        membership = db.execute(
            select(BillMembership).where(
                BillMembership.bill_id == payload.expected_bill_id,
                BillMembership.guest_session_id == guest.session_id,
            )
        ).scalar_one_or_none()
        if expected_bill is None or membership is None:
            db.rollback()
            raise AppError(
                status_code=404,
                code="NOT_FOUND",
                message="Không tìm thấy hóa đơn thuộc phiên khách hiện tại.",
                details={},
            )
        if expected_bill.status == "paid":
            db.rollback()
            raise AppError(
                status_code=409,
                code="BILL_CLOSED",
                message="Hóa đơn đã thanh toán và đóng. Vui lòng bắt đầu lượt phục vụ mới.",
                details={"bill_id": str(expected_bill.id), "status": "paid"},
            )

    current_open_bill = db.execute(
        select(Bill)
        .where(Bill.table_id == table.id, Bill.status == "open")
        .with_for_update()
    ).scalar_one_or_none()

    if payload.expected_bill_id is None and current_open_bill is not None:
        db.rollback()
        raise AppError(
            status_code=409,
            code="TABLE_VISIT_CHANGED",
            message="Bàn vừa có hóa đơn mở mới. Vui lòng xác nhận tham gia lượt hiện tại.",
            details={"current_bill_id": str(current_open_bill.id)},
        )

    if payload.expected_bill_id is not None and (
        current_open_bill is None or current_open_bill.id != payload.expected_bill_id
    ):
        db.rollback()
        raise AppError(
            status_code=409,
            code="TABLE_VISIT_CHANGED",
            message="Phiên bàn đã thay đổi.",
            details={
                "current_bill_id": str(current_open_bill.id) if current_open_bill else None
            },
        )

    # Step 4: Lock menu_items in sorted UUID order
    unique_menu_ids = sorted({line.menu_item_id for line in payload.items}, key=lambda u: u.int)
    locked_menu_rows = list(
        db.execute(
            select(MenuItem)
            .where(MenuItem.id.in_(unique_menu_ids))
            .order_by(MenuItem.id.asc())
            .with_for_update()
        ).scalars().all()
    )
    menu_by_id = {m.id: m for m in locked_menu_rows}
    if after_menu_lock_hook is not None:
        after_menu_lock_hook()

    # Check existence and active status (422 VALIDATION_ERROR)
    missing_or_inactive: list[dict[str, Any]] = []
    for idx, line in enumerate(payload.items):
        m = menu_by_id.get(line.menu_item_id)
        if m is None or not m.active:
            missing_or_inactive.append(
                {"index": idx, "menu_item_id": str(line.menu_item_id), "reason": "not_found_or_inactive"}
            )
    if missing_or_inactive:
        db.rollback()
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Có món trong giỏ không tồn tại hoặc đã ngừng phục vụ.",
            details={"items": missing_or_inactive},
        )

    # Check availability first (409 ITEM_UNAVAILABLE takes precedence over PRICE_CHANGED)
    unavailable_items: list[dict[str, Any]] = []
    seen_unavail: set[uuid.UUID] = set()
    for line in payload.items:
        m = menu_by_id[line.menu_item_id]
        if not m.available and m.id not in seen_unavail:
            seen_unavail.add(m.id)
            unavailable_items.append({"menu_item_id": str(m.id), "reason": "unavailable"})
    if unavailable_items:
        db.rollback()
        raise AppError(
            status_code=409,
            code="ITEM_UNAVAILABLE",
            message="Có món vừa hết hàng. Vui lòng sửa giỏ.",
            details={"items": unavailable_items},
        )

    # Check expected price (409 PRICE_CHANGED)
    price_changed_items: list[dict[str, Any]] = []
    seen_price: set[uuid.UUID] = set()
    for line in payload.items:
        m = menu_by_id[line.menu_item_id]
        expected_price = int(line.expected_unit_price_vnd)
        if expected_price != m.price_vnd and m.id not in seen_price:
            seen_price.add(m.id)
            price_changed_items.append(
                {
                    "menu_item_id": str(m.id),
                    "reason": "price_changed",
                    "current_unit_price_vnd": format_money_vnd(m.price_vnd),
                }
            )
    if price_changed_items:
        db.rollback()
        raise AppError(
            status_code=409,
            code="PRICE_CHANGED",
            message="Giá món đã thay đổi. Vui lòng xác nhận lại giỏ hàng.",
            details={"items": price_changed_items},
        )

    # Calculate totals and validate limits
    existing_total_vnd = 0
    if current_open_bill is not None:
        _, _, existing_items = _load_bill_orders_and_items(db, current_open_bill.id)
        existing_total_vnd = calculate_open_bill_total_vnd(
            (it.unit_price_vnd, it.quantity, it.status) for it in existing_items
        )

    new_order_total_vnd = sum(
        calculate_line_total_vnd(menu_by_id[line.menu_item_id].price_vnd, line.quantity)
        for line in payload.items
    )
    projected_bill_total_vnd = existing_total_vnd + new_order_total_vnd
    try:
        validate_order_lines_limits(len(payload.items), projected_bill_total_vnd)
    except AppError:
        db.rollback()
        raise

    now = utc_now()
    if current_open_bill is None:
        bill = Bill(
            id=uuid.uuid4(),
            table_id=table.id,
            shift_id=shift.id,
            status="open",
            version=1,
            opened_at=now,
            paid_at=None,
            total_vnd=None,
        )
        db.add(bill)
        db.flush()
        db.add(
            BillMembership(
                bill_id=bill.id,
                guest_session_id=guest.session_id,
                joined_at=now,
            )
        )
    else:
        bill = current_open_bill
        bill.version += 1
        db.flush()

    order = Order(
        id=uuid.uuid4(),
        bill_id=bill.id,
        created_by_session_id=guest.session_id,
        created_at=now,
    )
    db.add(order)
    db.flush()

    line_uuids = _sequential_uuid4s(len(payload.items))
    created_items: list[OrderItem] = []
    for line_id, line in zip(line_uuids, payload.items, strict=True):
        m = menu_by_id[line.menu_item_id]
        oi = OrderItem(
            id=line_id,
            order_id=order.id,
            menu_item_id=m.id,
            name_snapshot=m.name,
            unit_price_vnd=m.price_vnd,
            quantity=line.quantity,
            note=line.note,
            status="waiting",
            version=1,
            started_at=None,
            done_at=None,
            cancelled_at=None,
        )
        db.add(oi)
        created_items.append(oi)
    db.flush()

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="guest",
        principal_id=guest.session_id,
        action="order.create",
        resource_type="order",
        resource_id=order.id,
        before_state=None,
        after_state={
            "bill_id": str(bill.id),
            "bill_version": bill.version,
            "item_count": len(created_items),
            "total_vnd": format_money_vnd(projected_bill_total_vnd),
        },
    )

    events = [
        PendingDomainEvent(
            audience=aud,
            event_type="order.created",
            resource_type="order",
            resource_id=order.id,
            aggregate_version=1,
            bill_id=bill.id,
        )
        for aud in ("guest", "kitchen", "cashier")
    ]
    cursor = allocate_and_append_domain_events(
        db, events, after_clock_lock_hook=after_clock_lock_hook
    )

    response_body: dict[str, Any] = {
        "data": {
            "order": {
                "id": str(order.id),
                "order_number": str(order.order_number),
                "created_at": iso_utc(order.created_at),
                "items": [
                    serialize_guest_item(
                        it,
                        creator_session_id=guest.session_id,
                        viewer_session_id=guest.session_id,
                        bill_status=bill.status,
                    )
                    for it in created_items
                ],
            },
            "bill": {
                "id": str(bill.id),
                "table_number": table.number,
                "status": bill.status,
                "version": bill.version,
                "total_vnd": format_money_vnd(projected_bill_total_vnd),
                "can_pay": False,
            },
            "event_cursor": cursor,
        }
    }
    complete_idempotency_reservation(
        db, reservation_id=res_id, response_status=201, response_json=response_body
    )
    commit_or_translate(db, before_commit_hook=before_commit_hook)
    return 201, response_body, False


def get_guest_bill_snapshot(
    db: Session, guest: GuestPrincipal, bill_id: uuid.UUID
) -> dict[str, Any]:
    with repeatable_read_snapshot(db) as snap:
        cursor = str(read_event_watermark(snap))
        membership = snap.execute(
            select(BillMembership).where(
                BillMembership.bill_id == bill_id,
                BillMembership.guest_session_id == guest.session_id,
            )
        ).scalar_one_or_none()
        if membership is None:
            raise AppError(
                status_code=404,
                code="NOT_FOUND",
                message="Không tìm thấy hóa đơn thuộc phiên khách hiện tại.",
                details={},
            )

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
            bill.status,
            shift_open,
            bool(orders),
            (it.status for it in all_items),
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
                        "items": [
                            serialize_guest_item(
                                it,
                                creator_session_id=o.created_by_session_id,
                                viewer_session_id=guest.session_id,
                                bill_status=bill.status,
                            )
                            for it in by_order[o.id]
                        ],
                    }
                    for o in orders
                ],
                "payment": serialize_payment(payment) if payment is not None else None,
                "event_cursor": cursor,
            }
        }


def cancel_guest_item(
    request: Request,
    db: Session,
    guest: GuestPrincipal,
    item_id: uuid.UUID,
    payload: ItemVersionInput,
    *,
    after_item_lock_hook: Callable[[], None] | None = None,
) -> tuple[int, dict[str, Any], bool]:
    # Pre-check item exists, guest has membership on parent bill, and guest is creator of parent order
    preview = db.execute(
        select(OrderItem.id, Order.bill_id, Order.created_by_session_id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.id == item_id)
    ).first()
    if preview is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy dòng món thuộc quyền hủy của bạn.",
            details={},
        )
    _, bill_id, creator_session_id = preview
    membership = db.execute(
        select(BillMembership).where(
            BillMembership.bill_id == bill_id,
            BillMembership.guest_session_id == guest.session_id,
        )
    ).scalar_one_or_none()
    db.rollback()

    if membership is None or creator_session_id != guest.session_id:
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy dòng món thuộc quyền hủy của bạn.",
            details={},
        )

    idem_key = parse_idempotency_key(request)
    operation = f"POST:/api/v1/guest/items/{item_id}/cancel"
    res_id, replay_status, replay_body = reserve_or_replay_idempotency(
        db,
        principal_kind="guest",
        principal_id=guest.session_id,
        operation=operation,
        key=idem_key,
        payload={"expected_version": payload.expected_version},
    )
    if replay_status is not None and replay_body is not None:
        return replay_status, replay_body, True
    assert res_id is not None

    # Lock order: bill FOR UPDATE -> order_item FOR UPDATE
    bill_row = db.execute(
        select(Bill, DiningTable.number)
        .join(DiningTable, Bill.table_id == DiningTable.id)
        .where(Bill.id == bill_id)
        .with_for_update(of=Bill)
    ).first()
    if bill_row is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy hóa đơn.",
            details={},
        )
    bill, table_number = bill_row

    item_row = db.execute(
        select(OrderItem, Order.created_by_session_id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.id == item_id, Order.bill_id == bill.id)
        .with_for_update(of=OrderItem)
    ).first()
    if item_row is None:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy dòng món.",
            details={},
        )
    item, creator_id = item_row
    if creator_id != guest.session_id:
        db.rollback()
        raise AppError(
            status_code=404,
            code="NOT_FOUND",
            message="Không tìm thấy dòng món thuộc quyền hủy của bạn.",
            details={},
        )

    if after_item_lock_hook is not None:
        after_item_lock_hook()

    if bill.status != "open":
        db.rollback()
        raise AppError(
            status_code=409,
            code="BILL_CLOSED",
            message="Hóa đơn đã thanh toán, không thể hủy món.",
            details={"bill_id": str(bill.id), "status": bill.status},
        )

    # Check expected_version before state conflict per api-design.md section 5
    if item.version != payload.expected_version:
        db.rollback()
        raise AppError(
            status_code=409,
            code="VERSION_CONFLICT",
            message="Trạng thái dòng món đã thay đổi.",
            details={"current_version": item.version, "current_status": item.status},
        )

    try:
        validate_guest_cancel_state(bill.status, item.status)
    except AppError:
        db.rollback()
        raise

    now = utc_now()
    before_ver = item.version
    item.status = "cancelled"
    item.cancelled_at = now
    item.version += 1
    bill.version += 1
    db.flush()

    orders, _, all_items = _load_bill_orders_and_items(db, bill.id)
    new_total_vnd = calculate_open_bill_total_vnd(
        (it.unit_price_vnd, it.quantity, it.status) for it in all_items
    )
    shift_open = is_any_shift_open(db)
    can_pay = compute_bill_can_pay(
        bill.status, shift_open, bool(orders), (it.status for it in all_items)
    )

    append_audit_event(
        db,
        request_id=get_request_id(request),
        principal_kind="guest",
        principal_id=guest.session_id,
        action="item.cancel",
        resource_type="order_item",
        resource_id=item.id,
        before_state={"status": "waiting", "version": before_ver},
        after_state={
            "status": "cancelled",
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
            "item": serialize_guest_item(
                item,
                creator_session_id=guest.session_id,
                viewer_session_id=guest.session_id,
                bill_status=bill.status,
            ),
            "bill": {
                "id": str(bill.id),
                "table_number": int(table_number),
                "status": bill.status,
                "version": bill.version,
                "total_vnd": format_money_vnd(new_total_vnd),
                "can_pay": can_pay,
            },
            "event_cursor": cursor,
        }
    }
    complete_idempotency_reservation(
        db, reservation_id=res_id, response_status=200, response_json=response_body
    )
    commit_or_translate(db)
    return 200, response_body, False

