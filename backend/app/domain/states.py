"""Pure domain state machine, permissions predicates, and time-of-day buckets."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo

from app.errors import AppError

LEGAL_KITCHEN_TRANSITIONS: dict[str, str] = {
    "waiting": "preparing",
    "preparing": "done",
}


def validate_kitchen_transition(current_status: str, target_status: str) -> None:
    if target_status not in {"preparing", "done"}:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Trạng thái pha chế đích không hợp lệ.",
            details={"field": "status"},
        )
    expected_target = LEGAL_KITCHEN_TRANSITIONS.get(current_status)
    if expected_target != target_status:
        raise AppError(
            status_code=409,
            code="INVALID_TRANSITION",
            message="Chuyển trạng thái pha chế không hợp lệ.",
            details={"current_status": current_status, "target_status": target_status},
        )


def can_guest_cancel_item(is_mine: bool, bill_status: str, item_status: str) -> bool:
    return bool(is_mine and bill_status == "open" and item_status == "waiting")


def validate_guest_cancel_state(bill_status: str, item_status: str) -> None:
    if bill_status != "open":
        raise AppError(
            status_code=409,
            code="BILL_CLOSED",
            message="Hóa đơn đã thanh toán, không thể hủy món.",
            details={"status": bill_status},
        )
    if item_status != "waiting":
        raise AppError(
            status_code=409,
            code="STATE_CONFLICT",
            message="Chỉ có thể hủy dòng món khi đang ở trạng thái chờ (waiting).",
            details={"current_status": item_status},
        )


def count_unfinished_items(item_statuses: Iterable[str]) -> int:
    return sum(1 for st in item_statuses if st in {"waiting", "preparing"})


def compute_bill_can_pay(
    bill_status: str,
    shift_open: bool,
    has_orders: bool,
    item_statuses: Iterable[str],
) -> bool:
    if bill_status != "open" or not shift_open or not has_orders:
        return False
    return count_unfinished_items(item_statuses) == 0


def derive_table_status(has_open_bill: bool, can_pay: bool) -> str:
    if not has_open_bill:
        return "free"
    if can_pay:
        return "ready_to_pay"
    return "serving"


def recommendation_bucket_for_bangkok_hour(hour: int) -> str:
    if 6 <= hour < 11:
        return "coffee"
    if 11 <= hour < 17:
        return "tea"
    return "other"


def recommendation_bucket_for_utc(now_utc: datetime, tz_name: str = "Asia/Bangkok") -> str:
    local_dt = now_utc.astimezone(ZoneInfo(tz_name))
    return recommendation_bucket_for_bangkok_hour(local_dt.hour)

