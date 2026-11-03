"""End-to-end PostgreSQL integration and concurrency tests (T01..T16, F01..F12)."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.main import app
from app.models import (
    AuditEvent,
    AuthSession,
    Bill,
    DiningTable,
    DomainEvent,
    MenuItem,
    Order,
    OrderItem,
    Payment,
    Shift,
    StaffUser,
)
from app.seed import _seed_uuid, run_seed
from app.services.common import PendingDomainEvent, allocate_and_append_domain_events

ORIGIN = "http://127.0.0.1:5173"


def _make_client() -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8000", raise_server_exceptions=False)


def _login_staff(client: TestClient, username: str, password: str) -> str:
    boot = client.get("/api/v1/auth/bootstrap")
    assert boot.status_code == 200
    pre_csrf = boot.json()["data"]["csrf_token"]
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": ORIGIN, "X-CSRF-Token": pre_csrf},
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["csrf_token"])


def _bootstrap_guest(client: TestClient, qr_token: str) -> dict[str, Any]:
    resp = client.post(
        "/api/v1/guest/bootstrap",
        json={"qr_token": qr_token},
        headers={"Origin": ORIGIN},
    )
    assert resp.status_code == 200, resp.text
    return dict(resp.json()["data"])


def _open_shift(cashier_client: TestClient, csrf: str) -> dict[str, Any]:
    resp = cashier_client.post(
        "/api/v1/cashier/shifts",
        json={},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 201, resp.text
    return dict(resp.json()["data"]["shift"])


def test_t01_f01_f10_health_seed_idempotency_qr_bootstrap_and_export(
    client: TestClient,
    db_session: Session,
    seed_tokens: dict[int, str],
) -> None:
    # Health live & ready
    assert client.get("/api/health/live").status_code == 200
    ready = client.get("/api/health/ready")
    assert ready.status_code == 200
    assert ready.json()["data"]["schema_revision"] == "0001_initial_schema"

    # Seed idempotency: running twice preserves counts and QR tokens
    tokens_second = run_seed(db_session)
    assert tokens_second == seed_tokens
    assert db_session.scalar(select(func.count()).select_from(DiningTable)) == 2
    assert db_session.scalar(select(func.count()).select_from(MenuItem)) == 12
    assert db_session.scalar(select(func.count()).select_from(StaffUser)) == 2

    # Guest bootstrap on Table 1 & Table 3 does NOT create an open bill
    data1 = _bootstrap_guest(client, seed_tokens[1])
    assert data1["table"]["number"] == 1
    assert data1["current_bill_id"] is None
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 0

    data3 = _bootstrap_guest(client, seed_tokens[3])
    assert data3["table"]["number"] == 3
    assert data3["current_bill_id"] is None

    # Invalid QR token returns 404 NOT_FOUND
    bad_qr = "A" * 43
    bad_resp = client.post(
        "/api/v1/guest/bootstrap",
        json={"qr_token": bad_qr},
        headers={"Origin": ORIGIN},
    )
    assert bad_resp.status_code == 404
    assert bad_resp.json()["error"]["code"] == "NOT_FOUND"

    # Disabled table returns 404 NOT_FOUND
    t3_id = _seed_uuid("table", "3")
    db_session.execute(
        text("UPDATE tables SET enabled = false WHERE id = :id"), {"id": t3_id}
    )
    db_session.commit()
    disabled_resp = client.post(
        "/api/v1/guest/bootstrap",
        json={"qr_token": seed_tokens[3]},
        headers={"Origin": ORIGIN},
    )
    assert disabled_resp.status_code == 404
    assert disabled_resp.json()["error"]["code"] == "NOT_FOUND"
    db_session.execute(
        text("UPDATE tables SET enabled = true WHERE id = :id"), {"id": t3_id}
    )
    db_session.commit()

    # Cashier QR export & audit log verification (no raw token leaked in audit_events)
    cashier_client = _make_client()
    cashier_csrf = _login_staff(cashier_client, "cashier.demo", "CashierDemo#2026")
    assert cashier_csrf

    t1_id = _seed_uuid("table", "1")
    qr_resp = cashier_client.get(f"/api/v1/cashier/tables/{t1_id}/qr")
    assert qr_resp.status_code == 200
    qr_data = qr_resp.json()["data"]
    assert qr_data["table_number"] == 1
    assert qr_data["url"].endswith(f"/t/{seed_tokens[1]}")

    audit_row = db_session.execute(
        select(AuditEvent).where(AuditEvent.action == "qr.export")
    ).scalar_one()
    assert seed_tokens[1] not in str(audit_row.after_state)


def test_t02_f02_staff_auth_csrf_origin_rbac_and_idor(
    db_session: Session,
    seed_tokens: dict[int, str],
) -> None:
    c_barista = _make_client()
    c_cashier = _make_client()

    # Wrong password -> 401 INVALID_CREDENTIALS
    boot = c_barista.get("/api/v1/auth/bootstrap")
    pre_csrf = boot.json()["data"]["csrf_token"]
    wrong_pw = c_barista.post(
        "/api/v1/auth/login",
        json={"username": "barista.demo", "password": "wrong-password"},
        headers={"Origin": ORIGIN, "X-CSRF-Token": pre_csrf},
    )
    assert wrong_pw.status_code == 401
    assert wrong_pw.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # Inactive staff -> 401 INVALID_CREDENTIALS
    db_session.execute(
        text("UPDATE staff_users SET active = false WHERE username = 'barista.demo'")
    )
    db_session.commit()
    boot2 = c_barista.get("/api/v1/auth/bootstrap")
    pre_csrf2 = boot2.json()["data"]["csrf_token"]
    inactive_resp = c_barista.post(
        "/api/v1/auth/login",
        json={"username": "barista.demo", "password": "BaristaDemo#2026"},
        headers={"Origin": ORIGIN, "X-CSRF-Token": pre_csrf2},
    )
    assert inactive_resp.status_code == 401
    db_session.execute(
        text("UPDATE staff_users SET active = true WHERE username = 'barista.demo'")
    )
    db_session.commit()

    # Successful login for barista & cashier
    barista_csrf = _login_staff(c_barista, "barista.demo", "BaristaDemo#2026")
    cashier_csrf = _login_staff(c_cashier, "cashier.demo", "CashierDemo#2026")

    # Missing CSRF or Evil Origin -> 403
    no_csrf = c_cashier.post(
        "/api/v1/cashier/shifts",
        json={},
        headers={"Origin": ORIGIN, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "CSRF_INVALID"

    bad_origin = c_cashier.post(
        "/api/v1/cashier/shifts",
        json={},
        headers={
            "Origin": "https://evil.example",
            "X-CSRF-Token": cashier_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert bad_origin.status_code == 403
    assert bad_origin.json()["error"]["code"] == "ORIGIN_INVALID"

    # RBAC: barista calling cashier -> 403 FORBIDDEN
    assert c_barista.get("/api/v1/cashier/tables").status_code == 403
    assert (
        c_barista.post(
            "/api/v1/cashier/shifts",
            json={},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": barista_csrf,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        ).status_code
        == 403
    )

    # RBAC: cashier calling kitchen -> 403 FORBIDDEN
    assert c_cashier.get("/api/v1/kitchen/queue").status_code == 403

    # IDOR: Guest B cannot read Guest A's bill without joining
    _open_shift(c_cashier, cashier_csrf)
    guest_a = _make_client()
    ga_boot = _bootstrap_guest(guest_a, seed_tokens[1])
    cf_sua_id = str(_seed_uuid("menu_item", "Cà phê:Cà phê sữa"))
    order_resp = guest_a.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": ga_boot["csrf_token"],
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert order_resp.status_code == 201
    bill_id = order_resp.json()["data"]["bill"]["id"]

    guest_b = _make_client()
    _bootstrap_guest(guest_b, seed_tokens[3])
    idor_resp = guest_b.get(f"/api/v1/guest/bills/{bill_id}")
    assert idor_resp.status_code == 404
    assert idor_resp.json()["error"]["code"] == "NOT_FOUND"

    # Logout revokes staff session
    logout_resp = c_barista.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": barista_csrf},
    )
    assert logout_resp.status_code == 204
    assert c_barista.get("/api/v1/auth/session").status_code == 401


def test_t03_f03_f06_validation_atomic_rejections_and_fault_rollback(
    db_session: Session,
    seed_tokens: dict[int, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    c_cashier = _make_client()
    cashier_csrf = _login_staff(c_cashier, "cashier.demo", "CashierDemo#2026")
    c_barista = _make_client()
    barista_csrf = _login_staff(c_barista, "barista.demo", "BaristaDemo#2026")

    guest = _make_client()
    g_boot = _bootstrap_guest(guest, seed_tokens[1])
    g_csrf = g_boot["csrf_token"]
    cf_sua_id = str(_seed_uuid("menu_item", "Cà phê:Cà phê sữa"))
    tra_dao_id = str(_seed_uuid("menu_item", "Trà trái cây:Trà đào"))

    # Shift closed -> 409 SHIFT_CLOSED
    closed_resp = guest.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert closed_resp.status_code == 409
    assert closed_resp.json()["error"]["code"] == "SHIFT_CLOSED"

    _open_shift(c_cashier, cashier_csrf)

    # Validation boundaries (qty 0, qty 21, note 251 chars) -> 422
    for bad_item in [
        {"menu_item_id": cf_sua_id, "quantity": 0, "note": "", "expected_unit_price_vnd": "30000"},
        {"menu_item_id": cf_sua_id, "quantity": 21, "note": "", "expected_unit_price_vnd": "30000"},
        {
            "menu_item_id": cf_sua_id,
            "quantity": 1,
            "note": "x" * 251,
            "expected_unit_price_vnd": "30000",
        },
    ]:
        val_resp = guest.post(
            "/api/v1/guest/orders",
            json={"qr_token": seed_tokens[1], "expected_bill_id": None, "items": [bad_item]},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": g_csrf,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
        assert val_resp.status_code == 422

    # Price mismatch -> 409 PRICE_CHANGED, 0 rows committed
    price_resp = guest.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "25000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert price_resp.status_code == 409
    assert price_resp.json()["error"]["code"] == "PRICE_CHANGED"
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 0

    # Barista marks Trà đào unavailable -> Guest multi-line order rejected atomically (0 rows)
    avail_resp = c_barista.patch(
        f"/api/v1/kitchen/menu/{tra_dao_id}/availability",
        json={"expected_version": 1, "available": False},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": barista_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert avail_resp.status_code == 200
    assert avail_resp.json()["data"]["item"]["version"] == 2

    # Idempotent no-op when setting available=False again with version 2
    noop_resp = c_barista.patch(
        f"/api/v1/kitchen/menu/{tra_dao_id}/availability",
        json={"expected_version": 2, "available": False},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": barista_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert noop_resp.status_code == 200
    assert noop_resp.json()["data"]["item"]["version"] == 2

    unavail_order = guest.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "30000",
                },
                {
                    "menu_item_id": tra_dao_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "35000",
                },
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert unavail_order.status_code == 409
    assert unavail_order.json()["error"]["code"] == "ITEM_UNAVAILABLE"
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 0
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert db_session.scalar(select(func.count()).select_from(OrderItem)) == 0

    # Fault injection mid-transaction before commit -> 500 & 0 partial rows
    import app.services.ordering_and_billing as ob_mod

    def _boom(*_args: Any, **_kwargs: Any) -> int:
        raise RuntimeError("injected mid-transaction failure before commit")

    monkeypatch.setattr(ob_mod, "allocate_and_append_domain_events", _boom)
    fault_resp = guest.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert fault_resp.status_code == 500
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 0
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0
    assert db_session.scalar(select(func.count()).select_from(OrderItem)) == 0


def test_t04_t05_f03_concurrent_first_submit_and_idempotency(
    db_session: Session,
    seed_tokens: dict[int, str],
) -> None:
    c_cashier = _make_client()
    cashier_csrf = _login_staff(c_cashier, "cashier.demo", "CashierDemo#2026")
    _open_shift(c_cashier, cashier_csrf)

    guest_a = _make_client()
    ga_csrf = _bootstrap_guest(guest_a, seed_tokens[1])["csrf_token"]
    guest_b = _make_client()
    gb_csrf = _bootstrap_guest(guest_b, seed_tokens[1])["csrf_token"]

    cf_sua_id = str(_seed_uuid("menu_item", "Cà phê:Cà phê sữa"))
    barrier = threading.Barrier(2)

    def _submit_first(client_obj: TestClient, csrf_tok: str) -> Any:
        barrier.wait(timeout=5)
        return client_obj.post(
            "/api/v1/guest/orders",
            json={
                "qr_token": seed_tokens[1],
                "expected_bill_id": None,
                "items": [
                    {
                        "menu_item_id": cf_sua_id,
                        "quantity": 1,
                        "note": "first submit race",
                        "expected_unit_price_vnd": "30000",
                    }
                ],
            },
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": csrf_tok,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_submit_first, guest_a, ga_csrf)
        f2 = pool.submit(_submit_first, guest_b, gb_csrf)
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 409], f"Expected [201, 409], got {[r1.status_code, r2.status_code]}"
    winner = r1 if r1.status_code == 201 else r2
    loser = r2 if r1.status_code == 201 else r1
    loser_client, loser_csrf = (guest_b, gb_csrf) if winner is r1 else (guest_a, ga_csrf)

    open_bill_id = winner.json()["data"]["bill"]["id"]
    assert loser.json()["error"]["code"] == "TABLE_VISIT_CHANGED"
    assert loser.json()["error"]["details"]["current_bill_id"] == open_bill_id

    # Loser explicitly joins open bill (and repeats join idempotently) then submits add-on order
    for _ in range(2):
        join_resp = loser_client.post(
            "/api/v1/guest/join",
            json={"qr_token": seed_tokens[1], "expected_bill_id": open_bill_id},
            headers={"Origin": ORIGIN, "X-CSRF-Token": loser_csrf},
        )
        assert join_resp.status_code == 200
        assert join_resp.json()["data"]["bill_id"] == open_bill_id

    idem_key = str(uuid.uuid4())
    addon_payload = {
        "qr_token": seed_tokens[1],
        "expected_bill_id": open_bill_id,
        "items": [
            {
                "menu_item_id": cf_sua_id,
                "quantity": 2,
                "note": "them 2 ly",
                "expected_unit_price_vnd": "30000",
            }
        ],
    }
    addon_resp = loser_client.post(
        "/api/v1/guest/orders",
        json=addon_payload,
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": loser_csrf,
            "Idempotency-Key": idem_key,
        },
    )
    assert addon_resp.status_code == 201
    assert addon_resp.headers.get("Idempotency-Replayed") is None
    assert addon_resp.json()["data"]["bill"]["total_vnd"] == "90000"

    # Idempotency replay returns exact 201 with Idempotency-Replayed: true and does not duplicate order
    replay_resp = loser_client.post(
        "/api/v1/guest/orders",
        json=addon_payload,
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": loser_csrf,
            "Idempotency-Key": idem_key,
        },
    )
    assert replay_resp.status_code == 201
    assert replay_resp.headers.get("Idempotency-Replayed") == "true"
    assert replay_resp.json() == addon_resp.json()

    # Same Idempotency-Key with different payload -> 409 IDEMPOTENCY_CONFLICT
    conflict_resp = loser_client.post(
        "/api/v1/guest/orders",
        json={
            **addon_payload,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 3,
                    "note": "khac payload",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": loser_csrf,
            "Idempotency-Key": idem_key,
        },
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 1
    assert db_session.scalar(select(func.count()).select_from(Order)) == 2


def test_t06_t07_f04_f05_cancel_vs_barista_start_race_and_fifo_pagination(
    db_session: Session,
    seed_tokens: dict[int, str],
) -> None:
    c_cashier = _make_client()
    cashier_csrf = _login_staff(c_cashier, "cashier.demo", "CashierDemo#2026")
    _open_shift(c_cashier, cashier_csrf)

    c_barista = _make_client()
    barista_csrf = _login_staff(c_barista, "barista.demo", "BaristaDemo#2026")

    guest_a = _make_client()
    ga_csrf = _bootstrap_guest(guest_a, seed_tokens[1])["csrf_token"]
    guest_b = _make_client()
    gb_csrf = _bootstrap_guest(guest_b, seed_tokens[1])["csrf_token"]

    cf_sua_id = str(_seed_uuid("menu_item", "Cà phê:Cà phê sữa"))
    tra_dao_id = str(_seed_uuid("menu_item", "Trà trái cây:Trà đào"))

    # Guest A creates multi-item order (ticket 1)
    r_order1 = guest_a.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "mon 1",
                    "expected_unit_price_vnd": "30000",
                },
                {
                    "menu_item_id": tra_dao_id,
                    "quantity": 1,
                    "note": "mon 2",
                    "expected_unit_price_vnd": "35000",
                },
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": ga_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert r_order1.status_code == 201
    bill_id = r_order1.json()["data"]["bill"]["id"]
    item1_id = r_order1.json()["data"]["order"]["items"][0]["id"]

    # Guest B joins same bill and places ticket 2
    guest_b.post(
        "/api/v1/guest/join",
        json={"qr_token": seed_tokens[1], "expected_bill_id": bill_id},
        headers={"Origin": ORIGIN, "X-CSRF-Token": gb_csrf},
    )
    r_order2 = guest_b.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": bill_id,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "mon cua B",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": gb_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert r_order2.status_code == 201

    # Ownership check: Guest B cannot cancel Guest A's item -> 404 NOT_FOUND (anti-IDOR)
    not_owner = guest_b.post(
        f"/api/v1/guest/items/{item1_id}/cancel",
        json={"expected_version": 1},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": gb_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert not_owner.status_code == 404
    assert not_owner.json()["error"]["code"] == "NOT_FOUND"

    # FIFO pagination check: limit=1 returns ticket 1 with BOTH of its items intact!
    q_page1 = c_barista.get("/api/v1/kitchen/queue?limit=1")
    assert q_page1.status_code == 200
    t_list1 = q_page1.json()["data"]
    assert len(t_list1) == 1
    assert len(t_list1[0]["items"]) == 2
    next_cursor = q_page1.json()["meta"]["next_cursor"]
    assert next_cursor is not None

    q_page2 = c_barista.get(f"/api/v1/kitchen/queue?limit=1&cursor={next_cursor}")
    assert q_page2.status_code == 200
    assert len(q_page2.json()["data"]) == 1

    # Invalid transition waiting -> done returns 409 INVALID_TRANSITION
    bad_trans = c_barista.patch(
        f"/api/v1/kitchen/items/{item1_id}/status",
        json={"expected_version": 1, "status": "done"},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": barista_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert bad_trans.status_code == 409
    assert bad_trans.json()["error"]["code"] == "INVALID_TRANSITION"

    # Concurrent race: Guest A cancels item1 vs Barista starts item1 (waiting -> preparing)
    barrier = threading.Barrier(2)

    def _guest_cancel() -> Any:
        barrier.wait(timeout=5)
        return guest_a.post(
            f"/api/v1/guest/items/{item1_id}/cancel",
            json={"expected_version": 1},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": ga_csrf,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )

    def _barista_start() -> Any:
        barrier.wait(timeout=5)
        return c_barista.patch(
            f"/api/v1/kitchen/items/{item1_id}/status",
            json={"expected_version": 1, "status": "preparing"},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": barista_csrf,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        fc = pool.submit(_guest_cancel)
        fb = pool.submit(_barista_start)
        rc, rb = fc.result(), fb.result()

    assert sorted([rc.status_code, rb.status_code]) == [200, 409]
    db_session.expire_all()
    item_row = db_session.get(OrderItem, uuid.UUID(item1_id))
    assert item_row is not None
    assert item_row.version == 2
    assert item_row.status in {"cancelled", "preparing"}


def test_t09_t10_t11_f07_f08_payment_guards_zero_bill_and_shift_races(
    db_session: Session,
    seed_tokens: dict[int, str],
) -> None:
    c_cashier1 = _make_client()
    csrf1 = _login_staff(c_cashier1, "cashier.demo", "CashierDemo#2026")
    c_cashier2 = _make_client()
    csrf2 = _login_staff(c_cashier2, "cashier.demo", "CashierDemo#2026")

    # T11: Concurrent open shift -> 1 wins 201, 1 gets 409 SHIFT_ALREADY_OPEN
    barrier = threading.Barrier(2)

    def _open_race(c: TestClient, tok: str) -> Any:
        barrier.wait(timeout=5)
        return c.post(
            "/api/v1/cashier/shifts",
            json={},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": tok,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        fs1 = pool.submit(_open_race, c_cashier1, csrf1)
        fs2 = pool.submit(_open_race, c_cashier2, csrf2)
        rs1, rs2 = fs1.result(), fs2.result()

    assert sorted([rs1.status_code, rs2.status_code]) == [201, 409]
    shift_winner = rs1 if rs1.status_code == 201 else rs2
    shift_loser = rs2 if rs1.status_code == 201 else rs1
    assert shift_loser.json()["error"]["code"] == "SHIFT_ALREADY_OPEN"
    shift_id = shift_winner.json()["data"]["shift"]["id"]

    # Zero-total bill (all items cancelled) can be paid with 0 VND
    guest = _make_client()
    g_csrf = _bootstrap_guest(guest, seed_tokens[1])["csrf_token"]
    cf_sua_id = str(_seed_uuid("menu_item", "Cà phê:Cà phê sữa"))

    ord_resp = guest.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert ord_resp.status_code == 201
    bill_id = ord_resp.json()["data"]["bill"]["id"]
    item_id = ord_resp.json()["data"]["order"]["items"][0]["id"]

    # Cannot close shift while open bill exists -> 409 OPEN_BILLS_EXIST
    close_blocked = c_cashier1.post(
        f"/api/v1/cashier/shifts/{shift_id}/close",
        json={"expected_version": 1},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf1,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert close_blocked.status_code == 409
    assert close_blocked.json()["error"]["code"] == "OPEN_BILLS_EXIST"

    # Cannot pay while item is waiting -> 409 ITEMS_NOT_DONE
    pay_unfinished = c_cashier1.post(
        f"/api/v1/cashier/bills/{bill_id}/payments",
        json={"expected_bill_version": 1, "expected_total_vnd": "30000", "method": "cash"},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf1,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert pay_unfinished.status_code == 409
    assert pay_unfinished.json()["error"]["code"] == "ITEMS_NOT_DONE"

    # Guest cancels the only item -> bill total becomes 0, can_pay becomes True
    cancel_resp = guest.post(
        f"/api/v1/guest/items/{item_id}/cancel",
        json={"expected_version": 1},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["bill"]["total_vnd"] == "0"
    assert cancel_resp.json()["data"]["bill"]["can_pay"] is True
    bill_ver = cancel_resp.json()["data"]["bill"]["version"]

    # Amount mismatch -> 409 AMOUNT_CHANGED
    pay_mismatch = c_cashier1.post(
        f"/api/v1/cashier/bills/{bill_id}/payments",
        json={"expected_bill_version": bill_ver, "expected_total_vnd": "30000", "method": "cash"},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf1,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert pay_mismatch.status_code == 409
    assert pay_mismatch.json()["error"]["code"] == "AMOUNT_CHANGED"

    # Concurrent duplicate payments with different Idempotency-Keys -> 1 wins 201, 1 gets 409
    pay_barrier = threading.Barrier(2)

    def _pay_race(c: TestClient, tok: str) -> Any:
        pay_barrier.wait(timeout=5)
        return c.post(
            f"/api/v1/cashier/bills/{bill_id}/payments",
            json={"expected_bill_version": bill_ver, "expected_total_vnd": "0", "method": "cash"},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": tok,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        fp1 = pool.submit(_pay_race, c_cashier1, csrf1)
        fp2 = pool.submit(_pay_race, c_cashier2, csrf2)
        rp1, rp2 = fp1.result(), fp2.result()

    assert sorted([rp1.status_code, rp2.status_code]) == [201, 409]
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Payment)) == 1


def test_t12_f09_sse_framing_commit_inversion_scoping_and_cursor_reset(
    db_session: Session,
    seed_tokens: dict[int, str],
) -> None:
    # Prove commit-inversion safety: Tx1 begins first, Tx2 begins second;
    # both allocate domain_events.id only under event_clock FOR UPDATE at commit time.
    factory = get_session_factory()
    with factory() as s1, factory() as s2:
        t1_id = _seed_uuid("table", "1")
        t3_id = _seed_uuid("table", "3")
        # Tx2 allocates and commits first
        allocate_and_append_domain_events(
            s2,
            [
                PendingDomainEvent(
                    bill_id=None,
                    audience="cashier",
                    event_type="table.updated",
                    resource_type="table",
                    resource_id=t3_id,
                    aggregate_version=1,
                )
            ],
        )
        s2.commit()

        # Tx1 allocates and commits second
        allocate_and_append_domain_events(
            s1,
            [
                PendingDomainEvent(
                    bill_id=None,
                    audience="cashier",
                    event_type="table.updated",
                    resource_type="table",
                    resource_id=t1_id,
                    aggregate_version=1,
                )
            ],
        )
        s1.commit()

    events = (
        db_session.execute(select(DomainEvent).order_by(DomainEvent.id.asc())).scalars().all()
    )
    assert [e.id for e in events] == [1, 2]
    assert events[0].resource_id == _seed_uuid("table", "3")
    assert events[1].resource_id == _seed_uuid("table", "1")

    # Start shift & create open bills on Table 1 and Table 3 to test SSE scoping
    c_cashier = _make_client()
    cashier_csrf = _login_staff(c_cashier, "cashier.demo", "CashierDemo#2026")
    _open_shift(c_cashier, cashier_csrf)

    guest1 = _make_client()
    g1_csrf = _bootstrap_guest(guest1, seed_tokens[1])["csrf_token"]
    guest3 = _make_client()
    g3_csrf = _bootstrap_guest(guest3, seed_tokens[3])["csrf_token"]
    cf_sua_id = str(_seed_uuid("menu_item", "Cà phê:Cà phê sữa"))

    r1 = guest1.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g1_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    bill1_id = r1.json()["data"]["bill"]["id"]
    order1_id = r1.json()["data"]["order"]["id"]

    r3 = guest3.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[3],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g3_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    order3_id = r3.json()["data"]["order"]["id"]

    # Guest 1 SSE stream for bill1 only receives bill1 events, never bill3 events
    sse_resp = guest1.get(
        f"/api/v1/guest/bills/{bill1_id}/events?after=0",
        headers={"X-Test-SSE-Max-Ticks": "1"},
    )
    assert sse_resp.status_code == 200
    assert "text/event-stream" in sse_resp.headers["content-type"]
    body_text = sse_resp.text
    assert ": connected" in body_text
    assert "event: order.created" in body_text
    assert order1_id in body_text
    assert order3_id not in body_text

    # Future cursor triggers event: reset
    reset_resp = c_cashier.get(
        "/api/v1/cashier/events?after=999999",
        headers={"X-Test-SSE-Max-Ticks": "1"},
    )
    assert reset_resp.status_code == 200
    assert "event: reset" in reset_resp.text


def test_t13_t14_t16_full_two_table_rehearsal_and_p2_recommendations_and_report(
    db_session: Session,
    seed_tokens: dict[int, str],
) -> None:
    c_cashier = _make_client()
    cashier_csrf = _login_staff(c_cashier, "cashier.demo", "CashierDemo#2026")
    c_barista = _make_client()
    barista_csrf = _login_staff(c_barista, "barista.demo", "BaristaDemo#2026")

    # 1. Cashier opens shift
    shift = _open_shift(c_cashier, cashier_csrf)
    shift_id = shift["id"]

    cf_sua_id = str(_seed_uuid("menu_item", "Cà phê:Cà phê sữa"))
    tra_dao_id = str(_seed_uuid("menu_item", "Trà trái cây:Trà đào"))

    # 2. Table 1 orders 2 x Cà phê sữa (30000) + 1 x Trà đào (35000) = 95000
    guest1 = _make_client()
    g1_csrf = _bootstrap_guest(guest1, seed_tokens[1])["csrf_token"]
    o1_key = str(uuid.uuid4())
    o1_payload = {
        "qr_token": seed_tokens[1],
        "expected_bill_id": None,
        "items": [
            {
                "menu_item_id": cf_sua_id,
                "quantity": 2,
                "note": "it da",
                "expected_unit_price_vnd": "30000",
            },
            {
                "menu_item_id": tra_dao_id,
                "quantity": 1,
                "note": "",
                "expected_unit_price_vnd": "35000",
            },
        ],
    }
    r_o1 = guest1.post(
        "/api/v1/guest/orders",
        json=o1_payload,
        headers={"Origin": ORIGIN, "X-CSRF-Token": g1_csrf, "Idempotency-Key": o1_key},
    )
    assert r_o1.status_code == 201
    bill1_id = r_o1.json()["data"]["bill"]["id"]
    assert r_o1.json()["data"]["bill"]["total_vnd"] == "95000"
    t1_items = r_o1.json()["data"]["order"]["items"]

    # 3. Table 3 orders 1 x Trà đào (35000) = 35000
    guest3 = _make_client()
    g3_csrf = _bootstrap_guest(guest3, seed_tokens[3])["csrf_token"]
    r_o3 = guest3.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[3],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": tra_dao_id,
                    "quantity": 1,
                    "note": "",
                    "expected_unit_price_vnd": "35000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g3_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert r_o3.status_code == 201
    bill3_id = r_o3.json()["data"]["bill"]["id"]
    t3_item_id = r_o3.json()["data"]["order"]["items"][0]["id"]

    # 4. Barista completes Table 1 items (waiting -> preparing -> done)
    for it in t1_items:
        iid = it["id"]
        r_prep = c_barista.patch(
            f"/api/v1/kitchen/items/{iid}/status",
            json={"expected_version": 1, "status": "preparing"},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": barista_csrf,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
        assert r_prep.status_code == 200
        r_done = c_barista.patch(
            f"/api/v1/kitchen/items/{iid}/status",
            json={"expected_version": 2, "status": "done"},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": barista_csrf,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
        assert r_done.status_code == 200

    # 5. Cashier pays Table 1 (95000) -> Table 1 becomes free while Table 3 stays serving
    b1_snap = c_cashier.get(f"/api/v1/cashier/bills/{bill1_id}").json()["data"]
    assert b1_snap["can_pay"] is True
    assert b1_snap["total_vnd"] == "95000"

    pay1 = c_cashier.post(
        f"/api/v1/cashier/bills/{bill1_id}/payments",
        json={
            "expected_bill_version": b1_snap["version"],
            "expected_total_vnd": "95000",
            "method": "cash",
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": cashier_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert pay1.status_code == 201

    # Verify Idempotency replay of o1_key STILL returns 201 even after bill1 is paid!
    replay_after_paid = guest1.post(
        "/api/v1/guest/orders",
        json=o1_payload,
        headers={"Origin": ORIGIN, "X-CSRF-Token": g1_csrf, "Idempotency-Key": o1_key},
    )
    assert replay_after_paid.status_code == 201
    assert replay_after_paid.headers.get("Idempotency-Replayed") == "true"

    tables_snap = c_cashier.get("/api/v1/cashier/tables").json()["data"]
    by_num = {t["number"]: t for t in tables_snap}
    assert by_num[1]["status"] == "free"
    assert by_num[1]["bill_id"] is None
    assert by_num[3]["status"] == "serving"
    assert by_num[3]["bill_id"] == bill3_id

    # 6. Table 1 starts a NEW visit (1 x Cà phê sữa = 30000), finishes and pays
    r_visit2 = guest1.post(
        "/api/v1/guest/orders",
        json={
            "qr_token": seed_tokens[1],
            "expected_bill_id": None,
            "items": [
                {
                    "menu_item_id": cf_sua_id,
                    "quantity": 1,
                    "note": "luot 2",
                    "expected_unit_price_vnd": "30000",
                }
            ],
        },
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": g1_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert r_visit2.status_code == 201
    bill1_v2_id = r_visit2.json()["data"]["bill"]["id"]
    assert bill1_v2_id != bill1_id
    v2_item_id = r_visit2.json()["data"]["order"]["items"][0]["id"]

    for target_st, ver in [("preparing", 1), ("done", 2)]:
        assert (
            c_barista.patch(
                f"/api/v1/kitchen/items/{v2_item_id}/status",
                json={"expected_version": ver, "status": target_st},
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": barista_csrf,
                    "Idempotency-Key": str(uuid.uuid4()),
                },
            ).status_code
            == 200
        )

    b1_v2_snap = c_cashier.get(f"/api/v1/cashier/bills/{bill1_v2_id}").json()["data"]
    assert (
        c_cashier.post(
            f"/api/v1/cashier/bills/{bill1_v2_id}/payments",
            json={
                "expected_bill_version": b1_v2_snap["version"],
                "expected_total_vnd": "30000",
                "method": "cash",
            },
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": cashier_csrf,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        ).status_code
        == 201
    )

    # 7. Table 3 finishes and pays (35000)
    for target_st, ver in [("preparing", 1), ("done", 2)]:
        assert (
            c_barista.patch(
                f"/api/v1/kitchen/items/{t3_item_id}/status",
                json={"expected_version": ver, "status": target_st},
                headers={
                    "Origin": ORIGIN,
                    "X-CSRF-Token": barista_csrf,
                    "Idempotency-Key": str(uuid.uuid4()),
                },
            ).status_code
            == 200
        )

    b3_snap = c_cashier.get(f"/api/v1/cashier/bills/{bill3_id}").json()["data"]
    assert (
        c_cashier.post(
            f"/api/v1/cashier/bills/{bill3_id}/payments",
            json={
                "expected_bill_version": b3_snap["version"],
                "expected_total_vnd": "35000",
                "method": "cash",
            },
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": cashier_csrf,
                "Idempotency-Key": str(uuid.uuid4()),
            },
        ).status_code
        == 201
    )

    # 8. P2 F11 Recommendations check: returns up to 3 available items
    rec_resp = guest1.get("/api/v1/guest/recommendations")
    assert rec_resp.status_code == 200
    recs = rec_resp.json()["data"]["items"]
    assert 1 <= len(recs) <= 3
    assert all(r["item"]["available"] is True for r in recs)

    # 9. Cashier closes shift
    cur_shift = c_cashier.get("/api/v1/cashier/shifts/current").json()["data"]["shift"]
    close_resp = c_cashier.post(
        f"/api/v1/cashier/shifts/{shift_id}/close",
        json={"expected_version": cur_shift["version"]},
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": cashier_csrf,
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["data"]["shift"]["status"] == "closed"

    # 10. P2 F12 Shift Report check: 3 paid bills, 95000 + 30000 + 35000 = 160000 VND (no JOIN multiplication!)
    rep_resp = c_cashier.get(f"/api/v1/cashier/shifts/{shift_id}/report")
    assert rep_resp.status_code == 200
    rep = rep_resp.json()["data"]
    assert rep["paid_bill_count"] == 3
    assert rep["revenue_vnd"] == "160000"
    assert rep["top_items"][0]["name"] == "Cà phê sữa"
    assert rep["top_items"][0]["quantity"] == 3
    assert rep["top_items"][1]["name"] == "Trà đào"
    assert rep["top_items"][1]["quantity"] == 2
