"""Pytest fixtures and test database guard for TapOrder backend."""

from __future__ import annotations

import os
from collections.abc import Generator

DEV_DSN = "postgresql+psycopg://taporder:taporder_dev_local_only@127.0.0.1:5432/taporder_dev"
TEST_DSN = "postgresql+psycopg://taporder_test:taporder_test_local_only@127.0.0.1:5433/taporder_test"
os.environ["DATABASE_URL"] = TEST_DSN
os.environ["TEST_DATABASE_URL"] = TEST_DSN
os.environ["APP_ENV"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import assert_safe_test_dsn, get_settings  # noqa: E402
from app.db.session import dispose_engines, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.security.rate_limit import rate_limiter  # noqa: E402
from app.seed import SEED_MENU_ITEMS, run_seed, _seed_uuid  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[tuple[dict[int, str], str], None, None]:
    get_settings.cache_clear()
    settings = get_settings()
    assert_safe_test_dsn(settings.database_url, DEV_DSN)
    dispose_engines()
    session_factory = get_session_factory()
    with session_factory() as db:
        tokens = run_seed(db)
    yield tokens, settings.database_url
    dispose_engines()


@pytest.fixture()
def seed_tokens(setup_test_database: tuple[dict[int, str], str]) -> dict[int, str]:
    return setup_test_database[0]


@pytest.fixture()
def db_session(setup_test_database: tuple[dict[int, str], str]) -> Generator[Session, None, None]:
    rate_limiter.reset()
    session_factory = get_session_factory()
    with session_factory() as db:
        db.execute(
            text(
                """
                TRUNCATE TABLE
                    payments,
                    order_items,
                    orders,
                    bill_memberships,
                    bills,
                    shifts,
                    idempotency_records,
                    domain_events,
                    audit_events,
                    sessions,
                    preauth_sessions
                RESTART IDENTITY CASCADE
                """
            )
        )
        db.execute(text("UPDATE shift_guard SET version = 1 WHERE id = 1"))
        db.execute(
            text("UPDATE event_clock SET last_id = 0, retained_after = 0 WHERE id = 1")
        )
        db.execute(text("UPDATE staff_users SET active = true"))
        db.execute(text("UPDATE tables SET enabled = true"))
        for cat_name, item_name, desc, price_vnd, sort_order in SEED_MENU_ITEMS:
            item_id = _seed_uuid("menu_item", f"{cat_name}:{item_name}")
            db.execute(
                text(
                    """
                    UPDATE menu_items
                    SET price_vnd = :price_vnd,
                        available = true,
                        active = true,
                        sort_order = :sort_order,
                        version = 1
                    WHERE id = :item_id
                    """
                ),
                {
                    "price_vnd": price_vnd,
                    "sort_order": sort_order,
                    "item_id": item_id,
                },
            )
        db.commit()
        yield db


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    with TestClient(app, base_url="http://127.0.0.1:8000") as test_client:
        yield test_client
