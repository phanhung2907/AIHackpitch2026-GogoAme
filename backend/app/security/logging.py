"""Structured JSON logging with strict secret, QR token, cookie, CSRF, and note redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "qr_token",
    "qr_token_encrypted",
    "csrf_token",
    "x-csrf-token",
    "cookie",
    "set-cookie",
    "authorization",
    "note",
    "database_url",
    "test_database_url",
    "session_secret",
    "qr_encryption_key",
}

_QR_PATH_RE = re.compile(r"(/t/)[A-Za-z0-9_-]+")


def redact_path(path: str) -> str:
    return _QR_PATH_RE.sub(r"\1[REDACTED]", path)


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_KEYS:
            out[k] = "[REDACTED]"
        elif isinstance(v, dict):
            out[k] = redact_mapping(v)
        elif isinstance(v, list):
            out[k] = [redact_mapping(i) if isinstance(i, dict) else i for i in v]
        else:
            out[k] = v
    return out


def log_structured_request(
    logger: logging.Logger,
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    error_code: str | None = None,
) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "request_id": request_id,
        "method": method,
        "path": redact_path(path),
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    if error_code:
        record["error_code"] = error_code
    logger.info(json.dumps(record, ensure_ascii=False))

