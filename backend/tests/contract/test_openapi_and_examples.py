"""Contract tests verifying FastAPI OpenAPI parity, route coverage, and schema examples."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_PATH = REPO_ROOT / "contracts" / "openapi.yaml"
VALIDATE_SCRIPT_PATH = REPO_ROOT / "contracts" / "scripts" / "validate_and_generate.py"


def test_fastapi_openapi_json_matches_canonical_contract() -> None:
    canonical = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        runtime_spec = response.json()

    assert json.loads(json.dumps(runtime_spec, sort_keys=True)) == json.loads(
        json.dumps(canonical, sort_keys=True)
    )


def test_all_29_canonical_operations_registered_in_fastapi_router() -> None:
    canonical = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    registered: set[tuple[str, str]] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods or set():
                if method.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
                    registered.add((method.upper(), route.path))

    canonical_ops: set[tuple[str, str]] = set()
    for path, path_item in canonical["paths"].items():
        for method in path_item.keys():
            if method.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
                canonical_ops.add((method.upper(), path))

    assert len(canonical_ops) == 29
    assert canonical_ops == registered


def test_examples_and_typescript_codegen_are_in_sync() -> None:
    res = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"validate_and_generate.py failed:\n{res.stdout}\n{res.stderr}"
    assert "CONTRACT-1 OK" in res.stdout


def test_kitchen_dto_does_not_leak_financial_fields() -> None:
    canonical = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    schemas = canonical["components"]["schemas"]
    forbidden_fields = {
        "price_vnd",
        "unit_price_vnd",
        "total_vnd",
        "amount_vnd",
        "payment",
        "method",
    }
    for dto_name in [
        "KitchenMenuItemDTO",
        "KitchenItemDTO",
        "KitchenTicketDTO",
        "KitchenQueueResponse",
        "KitchenMenuResponse",
    ]:
        props = set(schemas[dto_name].get("properties", {}).keys())
        assert props.isdisjoint(forbidden_fields), f"{dto_name} leaked {props & forbidden_fields}"
