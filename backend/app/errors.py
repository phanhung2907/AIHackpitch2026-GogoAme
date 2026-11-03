"""Canonical domain and API exceptions mapped to ErrorEnvelope."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Structured exception carrying HTTP status, canonical ErrorCode, message, and details."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers or {}

