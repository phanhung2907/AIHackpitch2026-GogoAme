"""Strict Pydantic v2 request and response schemas aligned with CONTRACT-1."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from app.domain.totals import sanitize_note

_MONEY_RE = re.compile(r"^(0|[1-9][0-9]*)$")
_POS_MONEY_RE = re.compile(r"^[1-9][0-9]*$")
_QR_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --- Inputs ---
class LoginInput(StrictSchema):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("username")
    @classmethod
    def _clean_username(cls, v: str) -> str:
        trimmed = v.strip().lower()
        if not trimmed or len(trimmed) > 80:
            raise ValueError("username must be 1..80 characters after trimming")
        return trimmed


class BootstrapGuestInput(StrictSchema):
    qr_token: str = Field(min_length=43, max_length=43)

    @field_validator("qr_token")
    @classmethod
    def _validate_qr(cls, v: str) -> str:
        if not _QR_TOKEN_RE.match(v):
            raise ValueError("qr_token must be 43 base64url characters")
        return v


class JoinInput(StrictSchema):
    qr_token: str = Field(min_length=43, max_length=43)
    expected_bill_id: uuid.UUID | None

    @field_validator("qr_token")
    @classmethod
    def _validate_qr(cls, v: str) -> str:
        if not _QR_TOKEN_RE.match(v):
            raise ValueError("qr_token must be 43 base64url characters")
        return v


class OrderLineInput(StrictSchema):
    menu_item_id: uuid.UUID
    quantity: StrictInt = Field(ge=1, le=20)
    note: str = Field(default="")
    expected_unit_price_vnd: str

    @field_validator("note")
    @classmethod
    def _validate_note(cls, v: str) -> str:
        return sanitize_note(v)

    @field_validator("expected_unit_price_vnd")
    @classmethod
    def _validate_price(cls, v: str) -> str:
        if not isinstance(v, str) or not _POS_MONEY_RE.match(v):
            raise ValueError("expected_unit_price_vnd must be a positive integer decimal string")
        val = int(v)
        if val < 1 or val > 10_000_000:
            raise ValueError("expected_unit_price_vnd must be between 1 and 10000000")
        return v


class OrderInput(StrictSchema):
    qr_token: str = Field(min_length=43, max_length=43)
    expected_bill_id: uuid.UUID | None
    items: list[OrderLineInput] = Field(min_length=1, max_length=50)

    @field_validator("qr_token")
    @classmethod
    def _validate_qr(cls, v: str) -> str:
        if not _QR_TOKEN_RE.match(v):
            raise ValueError("qr_token must be 43 base64url characters")
        return v


class ItemVersionInput(StrictSchema):
    expected_version: StrictInt = Field(ge=1)


class ItemStatusInput(StrictSchema):
    expected_version: StrictInt = Field(ge=1)
    status: Literal["preparing", "done"]


class AvailabilityInput(StrictSchema):
    expected_version: StrictInt = Field(ge=1)
    available: StrictBool


class PaymentInput(StrictSchema):
    expected_bill_version: StrictInt = Field(ge=1)
    expected_total_vnd: str
    method: Literal["cash"]

    @field_validator("expected_total_vnd")
    @classmethod
    def _validate_total(cls, v: str) -> str:
        if not isinstance(v, str) or not _MONEY_RE.match(v):
            raise ValueError("expected_total_vnd must be a non-negative integer decimal string")
        val = int(v)
        if val < 0 or val > 1_000_000_000:
            raise ValueError("expected_total_vnd must be between 0 and 1000000000")
        return v


class OpenShiftInput(StrictSchema):
    pass


class CloseShiftInput(StrictSchema):
    expected_version: StrictInt = Field(ge=1)


# --- DTO Projections ---
class StaffDTO(StrictSchema):
    id: str
    username: str
    role: Literal["barista", "cashier"]


class TableRefDTO(StrictSchema):
    id: str
    number: int
    label: str


class CategoryDTO(StrictSchema):
    id: str
    name: str
    sort_order: int


class GuestMenuItemDTO(StrictSchema):
    id: str
    category_id: str
    name: str
    description: str
    price_vnd: str
    available: bool
    version: int
    sort_order: int


class KitchenMenuItemDTO(StrictSchema):
    id: str
    category_id: str
    name: str
    available: bool
    version: int
    sort_order: int


class GuestItemDTO(StrictSchema):
    id: str
    menu_item_id: str
    name: str
    unit_price_vnd: str
    quantity: int
    note: str
    status: Literal["waiting", "preparing", "done", "cancelled"]
    version: int
    is_mine: bool
    can_cancel: bool


class CashierItemDTO(StrictSchema):
    id: str
    menu_item_id: str
    name: str
    unit_price_vnd: str
    quantity: int
    note: str
    status: Literal["waiting", "preparing", "done", "cancelled"]
    version: int


class KitchenItemDTO(StrictSchema):
    id: str
    menu_item_id: str
    name: str
    quantity: int
    note: str
    status: Literal["waiting", "preparing", "done", "cancelled"]
    version: int
    started_at: str | None


class GuestOrderDTO(StrictSchema):
    id: str
    order_number: str
    created_at: str
    items: list[GuestItemDTO]


class CashierOrderDTO(StrictSchema):
    id: str
    order_number: str
    created_at: str
    items: list[CashierItemDTO]


class KitchenTicketDTO(StrictSchema):
    id: str
    order_number: str
    created_at: str
    table: TableRefDTO
    bill_id: str
    items: list[KitchenItemDTO]


class BillSummaryDTO(StrictSchema):
    id: str
    table_number: int
    status: Literal["open", "paid"]
    version: int
    total_vnd: str
    can_pay: bool


class PaidBillSummaryDTO(StrictSchema):
    id: str
    status: Literal["paid"]
    version: int
    total_vnd: str


class PaymentDTO(StrictSchema):
    id: str
    bill_id: str
    shift_id: str
    amount_vnd: str
    method: Literal["cash"]
    paid_at: str


class GuestBillDTO(StrictSchema):
    id: str
    table_id: str
    table_number: int
    status: Literal["open", "paid"]
    version: int
    opened_at: str
    paid_at: str | None
    total_vnd: str
    can_pay: bool
    orders: list[GuestOrderDTO]
    payment: PaymentDTO | None
    event_cursor: str


class CashierBillDTO(StrictSchema):
    id: str
    table_id: str
    table_number: int
    status: Literal["open", "paid"]
    version: int
    opened_at: str
    paid_at: str | None
    total_vnd: str
    can_pay: bool
    orders: list[CashierOrderDTO]
    payment: PaymentDTO | None
    event_cursor: str


class CashierTableDTO(StrictSchema):
    id: str
    number: int
    label: str
    status: Literal["free", "serving", "ready_to_pay"]
    bill_id: str | None
    total_vnd: str
    version: int | None
    can_pay: bool


class ShiftDTO(StrictSchema):
    id: str
    status: Literal["open", "closed"]
    opened_at: str
    closed_at: str | None
    version: int


class RecommendationEntryDTO(StrictSchema):
    item: GuestMenuItemDTO
    reason: Literal["time_of_day", "bestseller", "seed_order"]


class ReportTopItemDTO(StrictSchema):
    menu_item_id: str
    name: str
    quantity: int


class ErrorObject(StrictSchema):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str


class ErrorEnvelope(StrictSchema):
    error: ErrorObject

