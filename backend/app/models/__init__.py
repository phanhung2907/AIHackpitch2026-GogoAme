"""SQLAlchemy 2 declarative models matching docs/design/data-model.md."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DiningTable(Base):
    __tablename__ = "tables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    qr_token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False, unique=True)
    qr_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("number > 0", name="ck_tables_number_positive"),
        CheckConstraint("octet_length(qr_token_hash) = 32", name="ck_tables_qr_hash_len"),
    )


class StaffUser(Base):
    __tablename__ = "staff_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("username = lower(username)", name="ck_staff_users_username_lower"),
        CheckConstraint("role IN ('barista', 'cashier')", name="ck_staff_users_role"),
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    staff_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=True
    )
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("octet_length(token_hash) = 32", name="ck_sessions_token_hash_len"),
        CheckConstraint("octet_length(csrf_hash) = 32", name="ck_sessions_csrf_hash_len"),
        CheckConstraint(
            "(kind = 'guest' AND staff_user_id IS NULL) OR (kind = 'staff' AND staff_user_id IS NOT NULL)",
            name="ck_sessions_kind_staff_fk",
        ),
        CheckConstraint("expires_at > created_at", name="ck_sessions_expires_after_created"),
        Index("ix_sessions_expires_at", "expires_at"),
    )


class PreauthSession(Base):
    __tablename__ = "preauth_sessions"

    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), primary_key=True)
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("octet_length(token_hash) = 32", name="ck_preauth_token_hash_len"),
        CheckConstraint("octet_length(csrf_hash) = 32", name="ck_preauth_csrf_hash_len"),
        CheckConstraint("expires_at > created_at", name="ck_preauth_expires_after_created"),
    )


class ShiftGuard(Base):
    __tablename__ = "shift_guard"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_shift_guard_singleton"),
        CheckConstraint("version > 0", name="ck_shift_guard_version"),
    )


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    opened_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=False
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))

    __table_args__ = (
        CheckConstraint("version > 0", name="ck_shifts_version"),
        CheckConstraint(
            "(status = 'open' AND closed_by IS NULL AND closed_at IS NULL) OR "
            "(status = 'closed' AND closed_by IS NOT NULL AND closed_at IS NOT NULL AND closed_at >= opened_at)",
            name="ck_shifts_status_closed_fields",
        ),
        Index("ix_shifts_opened_at_id", "opened_at", "id"),
    )


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tables.id", ondelete="RESTRICT"), nullable=False
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default=text("'open'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_vnd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        CheckConstraint("version > 0", name="ck_bills_version"),
        CheckConstraint(
            "(status = 'open' AND paid_at IS NULL AND total_vnd IS NULL) OR "
            "(status = 'paid' AND paid_at IS NOT NULL AND total_vnd IS NOT NULL "
            "AND total_vnd >= 0 AND total_vnd <= 1000000000 AND paid_at >= opened_at)",
            name="ck_bills_status_paid_fields",
        ),
        Index("ix_bills_shift_status", "shift_id", "status"),
        Index("ix_bills_table_opened_id", "table_id", "opened_at", "id"),
    )


class BillMembership(Base):
    __tablename__ = "bill_memberships"

    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="RESTRICT"), primary_key=True
    )
    guest_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="RESTRICT"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_bill_memberships_guest_bill", "guest_session_id", "bill_id"),)


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    recommendation_bucket: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "recommendation_bucket IN ('coffee', 'tea', 'other')",
            name="ck_menu_categories_bucket",
        ),
        Index("ix_menu_categories_sort_id", "sort_order", "id"),
    )


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_categories.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default=text("''"))
    price_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("price_vnd > 0 AND price_vnd <= 10000000", name="ck_menu_items_price_bounds"),
        CheckConstraint("version > 0", name="ck_menu_items_version"),
        Index("ix_menu_items_cat_active_sort_id", "category_id", "active", "sort_order", "id"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    order_number: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False), nullable=False, unique=True
    )

    __table_args__ = (
        Index("ix_orders_bill_created_id", "bill_id", "created_at", "id"),
        Index("ix_orders_created_id", "created_at", "id"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False
    )
    name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String(250), nullable=False, default="", server_default=text("''"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting", server_default=text("'waiting'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "unit_price_vnd >= 1 AND unit_price_vnd <= 10000000",
            name="ck_order_items_price_bounds",
        ),
        CheckConstraint("quantity >= 1 AND quantity <= 20", name="ck_order_items_qty_bounds"),
        CheckConstraint("version > 0", name="ck_order_items_version"),
        CheckConstraint(
            "(status = 'waiting' AND started_at IS NULL AND done_at IS NULL AND cancelled_at IS NULL) OR "
            "(status = 'preparing' AND started_at IS NOT NULL AND done_at IS NULL AND cancelled_at IS NULL) OR "
            "(status = 'done' AND started_at IS NOT NULL AND done_at IS NOT NULL AND done_at >= started_at AND cancelled_at IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL AND started_at IS NULL AND done_at IS NULL)",
            name="ck_order_items_status_timestamps",
        ),
        Index("ix_order_items_order_id", "order_id", "id"),
        Index("ix_order_items_status_order", "status", "order_id"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False
    )
    cashier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_users.id", ondelete="RESTRICT"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="cash", server_default=text("'cash'"))
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("method = 'cash'", name="ck_payments_method_cash"),
        CheckConstraint("amount_vnd >= 0 AND amount_vnd <= 1000000000", name="ck_payments_amount_bounds"),
        Index("ix_payments_shift_paid_id", "shift_id", "paid_at", "id"),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    principal_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    principal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(160), nullable=False)
    key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    response_status: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("principal_kind", "principal_id", "operation", "key", name="uq_idempotency_scope_key"),
        CheckConstraint("principal_kind IN ('guest', 'staff')", name="ck_idempotency_principal_kind"),
        CheckConstraint("octet_length(payload_hash) = 32", name="ck_idempotency_hash_len"),
        CheckConstraint(
            "(response_status IS NULL AND response_json IS NULL) OR "
            "(response_status IN (200, 201) AND response_json IS NOT NULL)",
            name="ck_idempotency_response_completeness",
        ),
        Index("ix_idempotency_expires_at", "expires_at"),
    )


class EventClock(Base):
    __tablename__ = "event_clock"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    last_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    retained_after: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_event_clock_singleton"),
        CheckConstraint(
            "0 <= retained_after AND retained_after <= last_id",
            name="ck_event_clock_watermarks",
        ),
    )


class DomainEvent(Base):
    __tablename__ = "domain_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="RESTRICT"), nullable=True
    )
    audience: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "audience IN ('guest', 'kitchen', 'cashier', 'menu')",
            name="ck_domain_events_audience",
        ),
        CheckConstraint(
            "(audience != 'guest') OR (bill_id IS NOT NULL)",
            name="ck_domain_events_guest_bill_required",
        ),
        CheckConstraint("aggregate_version > 0", name="ck_domain_events_version"),
        Index("ix_domain_events_audience_id", "audience", "id"),
        Index("ix_domain_events_bill_id", "bill_id", "id"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    principal_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    principal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "principal_kind IN ('guest', 'staff', 'preauth', 'system')",
            name="ck_audit_events_principal_kind",
        ),
        Index("ix_audit_events_resource_created", "resource_type", "resource_id", "created_at"),
        Index("ix_audit_events_request_id", "request_id"),
    )

