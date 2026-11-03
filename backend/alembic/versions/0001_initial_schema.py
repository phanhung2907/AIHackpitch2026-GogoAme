"""Initial TapOrder schema, partial unique indexes, and singleton guards.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-11-03 09:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models import Base

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    # Partial unique index: at most one open shift across the entire cafe
    op.execute(
        sa.text("CREATE UNIQUE INDEX uq_shifts_single_open ON shifts ((1)) WHERE status = 'open'")
    )
    # Partial unique index: at most one open bill per table
    op.execute(
        sa.text("CREATE UNIQUE INDEX uq_bills_table_open ON bills (table_id) WHERE status = 'open'")
    )

    # Seed singleton concurrency guards before application startup
    op.execute(
        sa.text(
            "INSERT INTO shift_guard (id, version) VALUES (1, 1) ON CONFLICT (id) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO event_clock (id, last_id, retained_after) VALUES (1, 0, 0) ON CONFLICT (id) DO NOTHING"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(sa.text("DROP INDEX IF EXISTS uq_bills_table_open"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_shifts_single_open"))
    Base.metadata.drop_all(bind=bind)

