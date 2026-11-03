"""Pure domain functions for monetary amounts, snapshots, totals, and limits."""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.errors import AppError

MAX_UNIT_PRICE_VND = 10_000_000
MAX_LINE_QUANTITY = 20
MAX_LINE_TOTAL_VND = 200_000_000
MAX_LINES_PER_ORDER = 50
MAX_BILL_TOTAL_VND = 1_000_000_000
MAX_NOTE_LENGTH = 250

_MONEY_RE = re.compile(r"^(0|[1-9][0-9]*)$")


def parse_money_vnd(
    value: str,
    *,
    allow_zero: bool = True,
    max_vnd: int = MAX_BILL_TOTAL_VND,
    field_name: str = "amount_vnd",
) -> int:
    if not isinstance(value, str) or not _MONEY_RE.match(value):
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=f"Trường {field_name} phải là chuỗi số nguyên VND hợp lệ.",
            details={"field": field_name},
        )
    amount = int(value)
    min_vnd = 0 if allow_zero else 1
    if amount < min_vnd or amount > max_vnd:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=f"Giá trị {field_name} nằm ngoài giới hạn cho phép ({min_vnd}..{max_vnd}).",
            details={"field": field_name, "min": min_vnd, "max": max_vnd},
        )
    return amount


def format_money_vnd(amount: int) -> str:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ValueError(f"Invalid non-negative integer VND amount: {amount!r}")
    return str(amount)


def calculate_line_total_vnd(unit_price_vnd: int, quantity: int) -> int:
    if isinstance(unit_price_vnd, bool) or not isinstance(unit_price_vnd, int):
        raise ValueError("unit_price_vnd must be int")
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValueError("quantity must be int")
    if unit_price_vnd < 1 or unit_price_vnd > MAX_UNIT_PRICE_VND:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Đơn giá món vượt ngoài giới hạn hợp lệ.",
            details={"field": "unit_price_vnd"},
        )
    if quantity < 1 or quantity > MAX_LINE_QUANTITY:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Số lượng mỗi dòng phải từ 1 đến 20.",
            details={"field": "quantity"},
        )
    line_total = unit_price_vnd * quantity
    if line_total > MAX_LINE_TOTAL_VND:
        raise AppError(
            status_code=422,
            code="BILL_LIMIT_EXCEEDED",
            message="Thành tiền một dòng món vượt quá giới hạn 200.000.000 VND.",
            details={"max_line_total_vnd": str(MAX_LINE_TOTAL_VND)},
        )
    return line_total


def calculate_open_bill_total_vnd(items: Iterable[tuple[int, int, str]]) -> int:
    """Calculate integer VND total from (unit_price_vnd, quantity, status) tuples."""
    total = 0
    for unit_price_vnd, quantity, status in items:
        if status != "cancelled":
            total += calculate_line_total_vnd(unit_price_vnd, quantity)
    return total


def validate_order_lines_limits(num_lines: int, new_bill_total_vnd: int) -> None:
    if num_lines < 1 or num_lines > MAX_LINES_PER_ORDER:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Số dòng món trong một lượt gọi phải từ 1 đến 50.",
            details={"field": "items", "max_items": MAX_LINES_PER_ORDER},
        )
    if new_bill_total_vnd > MAX_BILL_TOTAL_VND:
        raise AppError(
            status_code=422,
            code="BILL_LIMIT_EXCEEDED",
            message="Tổng hóa đơn vượt quá giới hạn 1.000.000.000 VND.",
            details={
                "max_bill_total_vnd": str(MAX_BILL_TOTAL_VND),
                "projected_total_vnd": str(new_bill_total_vnd),
            },
        )


def sanitize_note(note: str | None) -> str:
    if note is None:
        return ""
    if not isinstance(note, str):
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Ghi chú phải là chuỗi văn bản.",
            details={"field": "note"},
        )
    trimmed = note.strip()
    if len(trimmed) > MAX_NOTE_LENGTH:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Ghi chú sau khi cắt khoảng trắng không được vượt quá 250 ký tự.",
            details={"field": "note", "max_length": MAX_NOTE_LENGTH},
        )
    return trimmed

