"""Unit tests for TapOrder domain logic, totals, state transitions, and security helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.config import assert_safe_test_dsn, get_settings
from app.domain.states import (
    can_guest_cancel_item,
    compute_bill_can_pay,
    derive_table_status,
    recommendation_bucket_for_utc,
    validate_guest_cancel_state,
    validate_kitchen_transition,
)
from app.domain.totals import (
    calculate_line_total_vnd,
    calculate_open_bill_total_vnd,
    format_money_vnd,
    parse_money_vnd,
    sanitize_note,
    validate_order_lines_limits,
)
from app.errors import AppError
from app.security.crypto import (
    decrypt_qr_token,
    derive_csrf_token,
    encrypt_qr_token,
    hash_password,
    sha256_bytes,
    verify_csrf_token,
    verify_password,
)
from app.security.logging import redact_mapping, redact_path


def test_parse_and_format_vnd_amount() -> None:
    assert parse_money_vnd("0") == 0
    assert parse_money_vnd("30000") == 30000
    assert format_money_vnd(95000) == "95000"

    for invalid in ["", "-1", "30000.5", "030000", "abc", "30,000"]:
        with pytest.raises(AppError) as exc_info:
            parse_money_vnd(invalid)
        assert exc_info.value.code == "VALIDATION_ERROR"


def test_line_and_bill_total_boundaries() -> None:
    assert calculate_line_total_vnd(30000, 1) == 30000
    assert calculate_line_total_vnd(30000, 20) == 600000

    for bad_qty in [0, -1, 21]:
        with pytest.raises(AppError) as exc_info:
            calculate_line_total_vnd(30000, bad_qty)
        assert exc_info.value.code == "VALIDATION_ERROR"

    # Line total ceiling 200,000,000
    assert calculate_line_total_vnd(10_000_000, 20) == 200_000_000
    with pytest.raises(AppError) as exc_info:
        calculate_line_total_vnd(10_000_001, 20)
    assert exc_info.value.code == "VALIDATION_ERROR"

    # Order lines count 1..50 and bill total ceiling 1,000,000,000
    validate_order_lines_limits(1, 30000)
    validate_order_lines_limits(50, 1_000_000_000)
    for bad_count in [0, 51]:
        with pytest.raises(AppError) as exc_info:
            validate_order_lines_limits(bad_count, 30000)
        assert exc_info.value.code == "VALIDATION_ERROR"

    with pytest.raises(AppError) as exc_info:
        validate_order_lines_limits(1, 1_000_000_001)
    assert exc_info.value.code == "BILL_LIMIT_EXCEEDED"

    # Bill total excludes cancelled items
    total = calculate_open_bill_total_vnd(
        [
            (30000, 2, "done"),
            (35000, 1, "waiting"),
            (45000, 1, "cancelled"),
        ]
    )
    assert total == 95000
    assert (
        calculate_open_bill_total_vnd(
            [
                (30000, 1, "cancelled"),
                (35000, 1, "cancelled"),
            ]
        )
        == 0
    )


def test_note_trimming_and_boundaries() -> None:
    assert sanitize_note(None) == ""
    assert sanitize_note("") == ""
    assert sanitize_note("    ") == ""
    assert sanitize_note("  it da  ") == "it da"
    note_250 = "a" * 250
    assert sanitize_note(f"  {note_250}  ") == note_250
    with pytest.raises(AppError) as exc_info:
        sanitize_note("a" * 251)
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_item_state_transitions_and_guards() -> None:
    validate_kitchen_transition("waiting", "preparing")
    validate_kitchen_transition("preparing", "done")

    invalid_pairs = [
        ("waiting", "done"),
        ("preparing", "preparing"),
        ("done", "preparing"),
        ("done", "done"),
        ("cancelled", "preparing"),
        ("cancelled", "done"),
    ]
    for cur, nxt in invalid_pairs:
        with pytest.raises(AppError) as exc_info:
            validate_kitchen_transition(cur, nxt)
        assert exc_info.value.code == "INVALID_TRANSITION"

    with pytest.raises(AppError) as exc_info:
        validate_kitchen_transition("waiting", "cancelled")
    assert exc_info.value.code == "VALIDATION_ERROR"

    assert can_guest_cancel_item(True, "open", "waiting") is True
    assert can_guest_cancel_item(False, "open", "waiting") is False
    assert can_guest_cancel_item(True, "paid", "waiting") is False
    assert can_guest_cancel_item(True, "open", "preparing") is False
    assert can_guest_cancel_item(True, "open", "done") is False
    assert can_guest_cancel_item(True, "open", "cancelled") is False

    validate_guest_cancel_state("open", "waiting")
    with pytest.raises(AppError) as exc_info:
        validate_guest_cancel_state("paid", "waiting")
    assert exc_info.value.code == "BILL_CLOSED"
    with pytest.raises(AppError) as exc_info:
        validate_guest_cancel_state("open", "preparing")
    assert exc_info.value.code == "STATE_CONFLICT"


def test_can_pay_and_derive_table_status() -> None:
    assert derive_table_status(has_open_bill=False, can_pay=False) == "free"
    assert derive_table_status(has_open_bill=True, can_pay=False) == "serving"
    assert derive_table_status(has_open_bill=True, can_pay=True) == "ready_to_pay"

    assert compute_bill_can_pay("open", True, False, []) is False
    assert compute_bill_can_pay("paid", True, True, ["done"]) is False
    assert compute_bill_can_pay("open", False, True, ["done"]) is False
    assert compute_bill_can_pay("open", True, True, ["waiting"]) is False
    assert compute_bill_can_pay("open", True, True, ["preparing"]) is False
    assert compute_bill_can_pay("open", True, True, ["done"]) is True
    assert compute_bill_can_pay("open", True, True, ["cancelled"]) is True
    assert compute_bill_can_pay("open", True, True, ["done", "cancelled"]) is True


def test_time_of_day_bucket_boundaries_asia_bangkok() -> None:
    tz = ZoneInfo("Asia/Bangkok")
    cases = [
        (datetime(2026, 4, 18, 5, 59, tzinfo=tz), "other"),
        (datetime(2026, 4, 18, 6, 0, tzinfo=tz), "coffee"),
        (datetime(2026, 4, 18, 10, 59, tzinfo=tz), "coffee"),
        (datetime(2026, 4, 18, 11, 0, tzinfo=tz), "tea"),
        (datetime(2026, 4, 18, 16, 59, tzinfo=tz), "tea"),
        (datetime(2026, 4, 18, 17, 0, tzinfo=tz), "other"),
    ]
    for local_dt, expected_bucket in cases:
        utc_dt = local_dt.astimezone(timezone.utc)
        assert recommendation_bucket_for_utc(utc_dt) == expected_bucket


def test_crypto_and_csrf_and_qr_encryption() -> None:
    settings = get_settings()
    pw_hash = hash_password("TapOrderBarista!2026")
    assert verify_password("TapOrderBarista!2026", pw_hash) is True
    assert verify_password("wrong-password", pw_hash) is False

    csrf = derive_csrf_token("raw_cookie_token", "staff", "user-123", settings.session_secret)
    csrf_hash = sha256_bytes(csrf)
    verify_csrf_token(csrf, csrf_hash)
    with pytest.raises(AppError) as exc_info:
        verify_csrf_token("invalid-csrf", csrf_hash)
    assert exc_info.value.code == "CSRF_INVALID"

    raw_qr = "taporder_demo_table_01_qr_token_v1"
    encrypted = encrypt_qr_token(raw_qr, settings.qr_encryption_key)
    assert decrypt_qr_token(encrypted, settings.qr_encryption_key) == raw_qr
    with pytest.raises(AppError) as exc_info:
        decrypt_qr_token("k1:invalid:payload", settings.qr_encryption_key)
    assert exc_info.value.status_code == 503


def test_dsn_guard_and_log_redaction() -> None:
    assert_safe_test_dsn(
        "postgresql+psycopg://taporder_test:taporder_test_local_only@127.0.0.1:5433/taporder_test",
        "postgresql+psycopg://taporder:taporder_dev_local_only@127.0.0.1:5432/taporder_dev",
    )
    with pytest.raises(RuntimeError):
        assert_safe_test_dsn(
            "postgresql+psycopg://taporder:taporder_dev_local_only@127.0.0.1:5432/taporder_dev"
        )
    with pytest.raises(RuntimeError):
        assert_safe_test_dsn(
            "postgresql+psycopg://taporder_test:taporder_test_local_only@127.0.0.1:5433/taporder_test",
            "postgresql+psycopg://taporder_test:taporder_test_local_only@127.0.0.1:5433/taporder_test",
        )

    redacted = redact_mapping(
        {
            "username": "barista.demo",
            "password": "secret-password",
            "qr_token": "raw_qr_token_value",
            "nested": {"cookie": "taporder_staff_session=xyz"},
        }
    )
    assert redacted["username"] == "barista.demo"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["qr_token"] == "[REDACTED]"
    assert redacted["nested"]["cookie"] == "[REDACTED]"

    assert redact_path("/t/secretToken12345") == "/t/[REDACTED]"
