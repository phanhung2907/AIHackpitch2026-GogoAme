"""Validate canonical OpenAPI 3.1 contract, generate/validate examples, and generate TypeScript types."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT_DIR / "contracts"
OPENAPI_PATH = CONTRACTS_DIR / "openapi.yaml"
EXAMPLES_DIR = CONTRACTS_DIR / "examples"
GENERATED_TS_PATH = CONTRACTS_DIR / "generated" / "api-types.ts"

# Stable fixture UUIDs (non-secret, deterministic)
UUID_TABLE_1 = "10000000-0000-4000-8000-000000000001"
UUID_TABLE_3 = "10000000-0000-4000-8000-000000000003"
UUID_CAT_COFFEE = "20000000-0000-4000-8000-000000000001"
UUID_CAT_TEA = "20000000-0000-4000-8000-000000000002"
UUID_ITEM_COFFEE = "30000000-0000-4000-8000-000000000001"
UUID_ITEM_TEA = "30000000-0000-4000-8000-000000000002"
UUID_GUEST_A = "40000000-0000-4000-8000-000000000001"
UUID_BARISTA = "50000000-0000-4000-8000-000000000001"
UUID_CASHIER = "50000000-0000-4000-8000-000000000002"
UUID_SHIFT_1 = "60000000-0000-4000-8000-000000000001"
UUID_BILL_1 = "70000000-0000-4000-8000-000000000001"
UUID_BILL_ZERO = "70000000-0000-4000-8000-000000000002"
UUID_ORDER_1 = "80000000-0000-4000-8000-000000000001"
UUID_ORDER_2 = "80000000-0000-4000-8000-000000000002"
UUID_LINE_1 = "90000000-0000-4000-8000-000000000001"
UUID_LINE_2 = "90000000-0000-4000-8000-000000000002"
UUID_PAY_1 = "a0000000-0000-4000-8000-000000000001"
UUID_PAY_ZERO = "a0000000-0000-4000-8000-000000000002"
FIXTURE_QR_TOKEN = "DEMO_FIXTURE_QR_TOKEN_43_CHARS_PLACEHOLDER_"


def build_examples() -> dict[str, tuple[str, dict[str, Any]]]:
    """Return mapping of filename -> (ComponentSchemaName, payload)."""
    return {
        "bootstrap_guest_null_bill.json": (
            "GuestBootstrapResponse",
            {
                "data": {
                    "guest_id": UUID_GUEST_A,
                    "csrf_token": "csrf-guest-fixture-token",
                    "expires_at": "2026-11-03T21:00:00Z",
                    "table": {"id": UUID_TABLE_1, "number": 1, "label": "Bàn 1"},
                    "current_bill_id": None,
                }
            },
        ),
        "bootstrap_guest_open_bill.json": (
            "GuestBootstrapResponse",
            {
                "data": {
                    "guest_id": UUID_GUEST_A,
                    "csrf_token": "csrf-guest-fixture-token",
                    "expires_at": "2026-11-03T21:00:00Z",
                    "table": {"id": UUID_TABLE_1, "number": 1, "label": "Bàn 1"},
                    "current_bill_id": UUID_BILL_1,
                }
            },
        ),
        "join_success.json": (
            "GuestJoinResponse",
            {"data": {"bill_id": UUID_BILL_1, "membership": True}},
        ),
        "join_empty.json": (
            "GuestJoinResponse",
            {"data": {"bill_id": None, "membership": False}},
        ),
        "order_submit_initial_request.json": (
            "OrderInput",
            {
                "qr_token": FIXTURE_QR_TOKEN,
                "expected_bill_id": None,
                "items": [
                    {
                        "menu_item_id": UUID_ITEM_COFFEE,
                        "quantity": 2,
                        "note": "Ít đá",
                        "expected_unit_price_vnd": "30000",
                    }
                ],
            },
        ),
        "order_submit_initial_response.json": (
            "OrderSubmitResponse",
            {
                "data": {
                    "order": {
                        "id": UUID_ORDER_1,
                        "order_number": "1",
                        "created_at": "2026-11-03T09:05:00Z",
                        "items": [
                            {
                                "id": UUID_LINE_1,
                                "menu_item_id": UUID_ITEM_COFFEE,
                                "name": "Cà phê sữa",
                                "unit_price_vnd": "30000",
                                "quantity": 2,
                                "note": "Ít đá",
                                "status": "waiting",
                                "version": 1,
                                "is_mine": True,
                                "can_cancel": True,
                            }
                        ],
                    },
                    "bill": {
                        "id": UUID_BILL_1,
                        "table_number": 1,
                        "status": "open",
                        "version": 1,
                        "total_vnd": "60000",
                        "can_pay": False,
                    },
                    "event_cursor": "3",
                }
            },
        ),
        "order_submit_addon_response.json": (
            "OrderSubmitResponse",
            {
                "data": {
                    "order": {
                        "id": UUID_ORDER_2,
                        "order_number": "2",
                        "created_at": "2026-11-03T09:10:00Z",
                        "items": [
                            {
                                "id": UUID_LINE_2,
                                "menu_item_id": UUID_ITEM_TEA,
                                "name": "Trà đào",
                                "unit_price_vnd": "35000",
                                "quantity": 1,
                                "note": "",
                                "status": "waiting",
                                "version": 1,
                                "is_mine": False,
                                "can_cancel": False,
                            }
                        ],
                    },
                    "bill": {
                        "id": UUID_BILL_1,
                        "table_number": 1,
                        "status": "open",
                        "version": 2,
                        "total_vnd": "95000",
                        "can_pay": False,
                    },
                    "event_cursor": "6",
                }
            },
        ),
        "guest_bill_mixed_ownership.json": (
            "GuestBillResponse",
            {
                "data": {
                    "id": UUID_BILL_1,
                    "table_id": UUID_TABLE_1,
                    "table_number": 1,
                    "status": "open",
                    "version": 2,
                    "opened_at": "2026-11-03T09:05:00Z",
                    "paid_at": None,
                    "total_vnd": "95000",
                    "can_pay": False,
                    "orders": [
                        {
                            "id": UUID_ORDER_1,
                            "order_number": "1",
                            "created_at": "2026-11-03T09:05:00Z",
                            "items": [
                                {
                                    "id": UUID_LINE_1,
                                    "menu_item_id": UUID_ITEM_COFFEE,
                                    "name": "Cà phê sữa",
                                    "unit_price_vnd": "30000",
                                    "quantity": 2,
                                    "note": "Ít đá",
                                    "status": "waiting",
                                    "version": 1,
                                    "is_mine": True,
                                    "can_cancel": True,
                                }
                            ],
                        },
                        {
                            "id": UUID_ORDER_2,
                            "order_number": "2",
                            "created_at": "2026-11-03T09:10:00Z",
                            "items": [
                                {
                                    "id": UUID_LINE_2,
                                    "menu_item_id": UUID_ITEM_TEA,
                                    "name": "Trà đào",
                                    "unit_price_vnd": "35000",
                                    "quantity": 1,
                                    "note": "",
                                    "status": "waiting",
                                    "version": 1,
                                    "is_mine": False,
                                    "can_cancel": False,
                                }
                            ],
                        },
                    ],
                    "payment": None,
                    "event_cursor": "6",
                }
            },
        ),
        "kitchen_queue_active.json": (
            "KitchenQueueResponse",
            {
                "data": [
                    {
                        "id": UUID_ORDER_1,
                        "order_number": "1",
                        "created_at": "2026-11-03T09:05:00Z",
                        "table": {"id": UUID_TABLE_1, "number": 1, "label": "Bàn 1"},
                        "bill_id": UUID_BILL_1,
                        "items": [
                            {
                                "id": UUID_LINE_1,
                                "menu_item_id": UUID_ITEM_COFFEE,
                                "name": "Cà phê sữa",
                                "quantity": 2,
                                "note": "Ít đá",
                                "status": "preparing",
                                "version": 2,
                                "started_at": "2026-11-03T09:06:00Z",
                            }
                        ],
                    }
                ],
                "meta": {"next_cursor": None, "limit": 50},
                "event_cursor": "9",
                "shift_open": True,
            },
        ),
        "kitchen_queue_empty.json": (
            "KitchenQueueResponse",
            {
                "data": [],
                "meta": {"next_cursor": None, "limit": 50},
                "event_cursor": "0",
                "shift_open": False,
            },
        ),
        "kitchen_menu_snapshot.json": (
            "KitchenMenuResponse",
            {
                "data": {
                    "items": [
                        {
                            "id": UUID_ITEM_COFFEE,
                            "category_id": UUID_CAT_COFFEE,
                            "name": "Cà phê sữa",
                            "available": True,
                            "version": 1,
                            "sort_order": 1,
                        }
                    ],
                    "event_cursor": "9",
                    "shift_open": True,
                }
            },
        ),
        "guest_menu_empty.json": (
            "GuestMenuResponse",
            {
                "data": {
                    "categories": [],
                    "items": [],
                    "version": "0",
                    "event_cursor": "0",
                    "shift_open": False,
                }
            },
        ),
        "cashier_bill_cancelled_zero.json": (
            "CashierBillResponse",
            {
                "data": {
                    "id": UUID_BILL_ZERO,
                    "table_id": UUID_TABLE_3,
                    "table_number": 3,
                    "status": "open",
                    "version": 2,
                    "opened_at": "2026-11-03T09:12:00Z",
                    "paid_at": None,
                    "total_vnd": "0",
                    "can_pay": True,
                    "orders": [
                        {
                            "id": UUID_ORDER_1,
                            "order_number": "1",
                            "created_at": "2026-11-03T09:12:00Z",
                            "items": [
                                {
                                    "id": UUID_LINE_1,
                                    "menu_item_id": UUID_ITEM_TEA,
                                    "name": "Trà đào",
                                    "unit_price_vnd": "35000",
                                    "quantity": 1,
                                    "note": "",
                                    "status": "cancelled",
                                    "version": 2,
                                }
                            ],
                        }
                    ],
                    "payment": None,
                    "event_cursor": "12",
                }
            },
        ),
        "payment_receipt_95000.json": (
            "PaymentReceiptResponse",
            {
                "data": {
                    "payment": {
                        "id": UUID_PAY_1,
                        "bill_id": UUID_BILL_1,
                        "shift_id": UUID_SHIFT_1,
                        "amount_vnd": "95000",
                        "method": "cash",
                        "paid_at": "2026-11-03T09:20:00Z",
                    },
                    "bill": {
                        "id": UUID_BILL_1,
                        "status": "paid",
                        "version": 6,
                        "total_vnd": "95000",
                    },
                    "table": {"number": 1, "status": "free"},
                    "event_cursor": "15",
                }
            },
        ),
        "payment_receipt_zero.json": (
            "PaymentReceiptResponse",
            {
                "data": {
                    "payment": {
                        "id": UUID_PAY_ZERO,
                        "bill_id": UUID_BILL_ZERO,
                        "shift_id": UUID_SHIFT_1,
                        "amount_vnd": "0",
                        "method": "cash",
                        "paid_at": "2026-11-03T09:22:00Z",
                    },
                    "bill": {
                        "id": UUID_BILL_ZERO,
                        "status": "paid",
                        "version": 3,
                        "total_vnd": "0",
                    },
                    "table": {"number": 3, "status": "free"},
                    "event_cursor": "18",
                }
            },
        ),
        "shift_report_empty.json": (
            "ShiftReportResponse",
            {
                "data": {
                    "shift": {
                        "id": UUID_SHIFT_1,
                        "status": "open",
                        "opened_at": "2026-11-03T09:00:00Z",
                        "closed_at": None,
                        "version": 1,
                    },
                    "revenue_vnd": "0",
                    "paid_bill_count": 0,
                    "top_items": [],
                    "as_of": "2026-11-03T09:30:00Z",
                    "event_cursor": "18",
                }
            },
        ),
        "error_409_table_visit_changed.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "TABLE_VISIT_CHANGED",
                    "message": "Phiên bàn đã thay đổi. Vui lòng xác nhận tham gia lượt hiện tại.",
                    "details": {"current_bill_id": UUID_BILL_1},
                    "request_id": "req-409-visit",
                }
            },
        ),
        "error_409_bill_closed.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "BILL_CLOSED",
                    "message": "Hóa đơn đã thanh toán và đóng.",
                    "details": {"bill_id": UUID_BILL_1, "status": "paid"},
                    "request_id": "req-409-closed",
                }
            },
        ),
        "error_409_shift_closed.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "SHIFT_CLOSED",
                    "message": "Quán hiện chưa mở ca phục vụ.",
                    "details": {},
                    "request_id": "req-409-shift-closed",
                }
            },
        ),
        "error_409_shift_already_open.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "SHIFT_ALREADY_OPEN",
                    "message": "Đã có một ca đang mở.",
                    "details": {"shift_id": UUID_SHIFT_1},
                    "request_id": "req-409-shift-open",
                }
            },
        ),
        "error_409_open_bills_exist.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "OPEN_BILLS_EXIST",
                    "message": "Không thể đóng ca khi vẫn còn hóa đơn đang mở.",
                    "details": {"open_bill_count": 1},
                    "request_id": "req-409-open-bills",
                }
            },
        ),
        "error_409_item_unavailable.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "ITEM_UNAVAILABLE",
                    "message": "Có món vừa hết hàng. Vui lòng sửa giỏ.",
                    "details": {
                        "items": [{"menu_item_id": UUID_ITEM_COFFEE, "reason": "unavailable"}]
                    },
                    "request_id": "req-409-unavailable",
                }
            },
        ),
        "error_409_price_changed.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "PRICE_CHANGED",
                    "message": "Giá món đã thay đổi. Vui lòng xác nhận lại giỏ hàng.",
                    "details": {
                        "items": [
                            {
                                "menu_item_id": UUID_ITEM_COFFEE,
                                "reason": "price_changed",
                                "current_unit_price_vnd": "32000",
                            }
                        ]
                    },
                    "request_id": "req-409-price",
                }
            },
        ),
        "error_409_version_conflict.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "VERSION_CONFLICT",
                    "message": "Dữ liệu đã được cập nhật bởi thao tác khác.",
                    "details": {"current_version": 2},
                    "request_id": "req-409-version",
                }
            },
        ),
        "error_409_state_conflict.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "STATE_CONFLICT",
                    "message": "Trạng thái hiện tại không cho phép thực hiện thao tác này.",
                    "details": {"current_status": "preparing"},
                    "request_id": "req-409-state",
                }
            },
        ),
        "error_409_invalid_transition.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "INVALID_TRANSITION",
                    "message": "Chuyển trạng thái pha chế không hợp lệ.",
                    "details": {"current_status": "waiting", "target_status": "done"},
                    "request_id": "req-409-transition",
                }
            },
        ),
        "error_409_items_not_done.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "ITEMS_NOT_DONE",
                    "message": "Chưa thể thanh toán khi vẫn còn món đang chờ hoặc đang pha.",
                    "details": {"unfinished_count": 1},
                    "request_id": "req-409-unfinished",
                }
            },
        ),
        "error_409_amount_changed.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "AMOUNT_CHANGED",
                    "message": "Tổng tiền hóa đơn đã thay đổi.",
                    "details": {"current_total_vnd": "95000"},
                    "request_id": "req-409-amount",
                }
            },
        ),
        "error_409_idempotency_conflict.json": (
            "ErrorEnvelope",
            {
                "error": {
                    "code": "IDEMPOTENCY_CONFLICT",
                    "message": "Idempotency-Key đã được dùng cho một nội dung lệnh khác.",
                    "details": {},
                    "request_id": "req-409-idem",
                }
            },
        ),
        "sse_event_business.json": (
            "SseBusinessEventData",
            {
                "id": "42",
                "type": "item.updated",
                "resource_id": UUID_LINE_1,
                "version": 2,
                "occurred_at": "2026-11-03T09:06:00Z",
            },
        ),
        "sse_event_checkpoint.json": (
            "SseCheckpointEventData",
            {"cursor": "45"},
        ),
        "sse_event_reset.json": (
            "SseControlEventData",
            {"reason": "cursor_out_of_range"},
        ),
        "sse_event_session_expired.json": (
            "SseControlEventData",
            {"reason": "session_expired"},
        ),
    }


SSE_FRAMING_EXAMPLE = """\
: heartbeat

id: 42
event: item.updated
data: {"id":"42","type":"item.updated","resource_id":"90000000-0000-4000-8000-000000000001","version":2,"occurred_at":"2026-11-03T09:06:00Z"}

id: 45
event: checkpoint
data: {"cursor":"45"}

event: reset
data: {"reason":"cursor_out_of_range"}

event: session_expired
data: {"reason":"session_expired"}
"""


def _resolve_refs(node: Any, components: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            ref_path = node["$ref"]
            prefix = "#/components/schemas/"
            if not ref_path.startswith(prefix):
                raise ValueError(f"Unsupported $ref: {ref_path}")
            target_name = ref_path[len(prefix) :]
            return _resolve_refs(copy.deepcopy(components["schemas"][target_name]), components)
        return {k: _resolve_refs(v, components) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(item, components) for item in node]
    return node


def render_typescript_types(spec: dict[str, Any]) -> str:
    """Deterministic TypeScript declarations generated from canonical OpenAPI 3.1."""
    schemas: dict[str, Any] = spec["components"]["schemas"]
    lines: list[str] = [
        "// AUTO-GENERATED FROM contracts/openapi.yaml (CONTRACT-1) — DO NOT EDIT MANUALLY",
        "export const CONTRACT_REVISION = 'CONTRACT-1' as const;",
        "",
    ]

    def ts_type(schema: dict[str, Any], indent: int = 0) -> str:
        if "$ref" in schema:
            return schema["$ref"].split("/")[-1]
        if "anyOf" in schema:
            return " | ".join(ts_type(sub, indent) for sub in schema["anyOf"])
        if "enum" in schema:
            return " | ".join(json.dumps(v) for v in schema["enum"])
        t = schema.get("type")
        if isinstance(t, list):
            parts = []
            for sub_t in t:
                if sub_t == "null":
                    parts.append("null")
                else:
                    parts.append(ts_type({**schema, "type": sub_t}, indent))
            return " | ".join(parts)
        if t == "string":
            return "string"
        if t == "integer" or t == "number":
            return "number"
        if t == "boolean":
            return "boolean"
        if t == "array":
            item_t = ts_type(schema.get("items", {}), indent)
            return f"Array<{item_t}>"
        if t == "object":
            props = schema.get("properties", {})
            if not props:
                if schema.get("additionalProperties") is True:
                    return "Record<string, unknown>"
                return "Record<string, never>"
            req = set(schema.get("required", []))
            pad = "  " * (indent + 1)
            closing_pad = "  " * indent
            prop_lines = ["{"]
            for prop_name, prop_schema in props.items():
                opt = "" if prop_name in req else "?"
                prop_lines.append(f"{pad}{prop_name}{opt}: {ts_type(prop_schema, indent + 1)};")
            prop_lines.append(f"{closing_pad}}}")
            return "\n".join(prop_lines)
        return "unknown"

    for name, schema_def in schemas.items():
        rendered = ts_type(schema_def, 0)
        if rendered.startswith("{"):
            lines.append(f"export interface {name} {rendered}")
        else:
            lines.append(f"export type {name} = {rendered};")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def validate_all(write_files: bool = False) -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    assert spec["openapi"] == "3.1.0", "Must be OpenAPI 3.1.0"
    assert spec["info"]["x-contract-revision"] == "CONTRACT-1"

    paths = spec["paths"]
    business_ops = [
        (method.upper(), path)
        for path, item in paths.items()
        if path.startswith("/api/v1/")
        for method in item.keys()
        if method in {"get", "post", "patch", "put", "delete"}
    ]
    health_ops = [
        (method.upper(), path)
        for path, item in paths.items()
        if path.startswith("/api/health/")
        for method in item.keys()
        if method in {"get", "post", "patch", "put", "delete"}
    ]
    assert len(business_ops) == 27, f"Expected 27 business endpoints, got {len(business_ops)}"
    assert len(health_ops) == 2, f"Expected 2 health endpoints, got {len(health_ops)}"

    examples = build_examples()
    if write_files:
        EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        for filename, (_, payload) in examples.items():
            target = EXAMPLES_DIR / filename
            target.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        (EXAMPLES_DIR / "sse_stream_framing.txt").write_text(
            SSE_FRAMING_EXAMPLE, encoding="utf-8"
        )
        GENERATED_TS_PATH.parent.mkdir(parents=True, exist_ok=True)
        GENERATED_TS_PATH.write_text(render_typescript_types(spec), encoding="utf-8")

    # Validate every example file against resolved JSON Schema
    for filename, (schema_name, expected_payload) in examples.items():
        example_path = EXAMPLES_DIR / filename
        assert example_path.exists(), f"Missing example file: {example_path}"
        on_disk = json.loads(example_path.read_text(encoding="utf-8"))
        assert on_disk == expected_payload, f"Drift in example file: {filename}"
        resolved_schema = _resolve_refs(
            spec["components"]["schemas"][schema_name], spec["components"]
        )
        validator = jsonschema.Draft202012Validator(
            resolved_schema,
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )
        validator.validate(on_disk)

    # Validate kitchen DTO projections never contain price/money/payment/guest fields
    forbidden_kitchen_fields = {
        "price_vnd",
        "unit_price_vnd",
        "total_vnd",
        "amount_vnd",
        "payment",
        "is_mine",
        "can_cancel",
        "created_by_session_id",
        "guest_id",
    }
    for kitchen_schema in ("KitchenMenuItemDTO", "KitchenItemDTO", "KitchenTicketDTO"):
        props = set(spec["components"]["schemas"][kitchen_schema]["properties"].keys())
        leaked = props & forbidden_kitchen_fields
        assert not leaked, f"{kitchen_schema} leaked forbidden fields: {leaked}"

    # Validate generated TypeScript types have zero drift
    assert GENERATED_TS_PATH.exists(), f"Missing generated TS types: {GENERATED_TS_PATH}"
    expected_ts = render_typescript_types(spec)
    actual_ts = GENERATED_TS_PATH.read_text(encoding="utf-8")
    assert actual_ts == expected_ts, "Generated TypeScript types drifted from openapi.yaml"

    print(
        f"CONTRACT-1 OK: {len(business_ops)} business endpoints, "
        f"{len(health_ops)} health endpoints, {len(examples)} JSON examples + SSE framing validated."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write examples and generated types")
    args = parser.parse_args()
    try:
        validate_all(write_files=args.write)
    except Exception as exc:
        print(f"Contract validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
