"""Application configuration, strict startup validation, and test DSN guard."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse, urlunparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_psycopg_dsn(dsn: str) -> str:
    """Normalize PostgreSQL URL to postgresql+psycopg:// without logging credentials."""
    parsed = urlparse(dsn.strip())
    if parsed.scheme in {"postgres", "postgresql"}:
        parsed = parsed._replace(scheme="postgresql+psycopg")
    elif parsed.scheme != "postgresql+psycopg":
        raise ValueError(f"Unsupported database scheme '{parsed.scheme}'; expected postgresql+psycopg")
    if not parsed.hostname or not parsed.path or parsed.path == "/":
        raise ValueError("DATABASE_URL must include hostname and database name")
    return urlunparse(parsed)


def assert_safe_test_dsn(test_dsn: str, dev_dsn: str | None = None) -> str:
    """Refuse running integration/destructive test harness against dev/demo/prod databases."""
    normalized = normalize_psycopg_dsn(test_dsn)
    parsed = urlparse(normalized)
    db_name = (parsed.path or "").lstrip("/").lower()
    if "test" not in db_name:
        raise RuntimeError(
            f"Test DSN guard rejected database '{db_name}': integration test database name must contain 'test'."
        )
    for forbidden in ("dev", "demo", "prod", "production"):
        if db_name == f"taporder_{forbidden}" or db_name == forbidden:
            raise RuntimeError(
                f"Test DSN guard rejected database '{db_name}': refuses targeting dev/demo/production DB."
            )
    if dev_dsn:
        dev_parsed = urlparse(normalize_psycopg_dsn(dev_dsn))
        if (
            parsed.hostname == dev_parsed.hostname
            and (parsed.port or 5432) == (dev_parsed.port or 5432)
            and db_name == (dev_parsed.path or "").lstrip("/").lower()
        ):
            raise RuntimeError(
                "Test DSN guard rejected TEST_DATABASE_URL because it points to the same target as DATABASE_URL."
            )
    return normalized


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    demo_timezone: str = Field(default="Asia/Bangkok", alias="DEMO_TIMEZONE")
    enable_mocks: bool = Field(default=False, alias="ENABLE_MOCKS")

    database_url: str = Field(
        default="postgresql+psycopg://taporder:taporder_dev_local_only@127.0.0.1:5432/taporder_dev",
        alias="DATABASE_URL",
    )
    test_database_url: str = Field(
        default="postgresql+psycopg://taporder_test:taporder_test_local_only@127.0.0.1:5433/taporder_test",
        alias="TEST_DATABASE_URL",
    )

    session_secret: str = Field(
        default="dev-local-session-secret-at-least-32-bytes-long",
        alias="SESSION_SECRET",
    )
    qr_encryption_key: str = Field(
        default="k1:MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        alias="QR_ENCRYPTION_KEY",
    )
    qr_encryption_backup_keys: str = Field(
        default="",
        alias="QR_ENCRYPTION_BACKUP_KEYS",
    )

    public_base_url: str = Field(
        default="http://127.0.0.1:5173",
        alias="PUBLIC_BASE_URL",
    )
    allowed_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8080,http://127.0.0.1:8000,http://testserver",
        alias="ALLOWED_ORIGINS",
    )
    allowed_hosts: str = Field(
        default="127.0.0.1,localhost,testserver,backend",
        alias="ALLOWED_HOSTS",
    )
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")

    demo_barista_password: str = Field(default="", alias="DEMO_BARISTA_PASSWORD")
    demo_cashier_password: str = Field(default="", alias="DEMO_CASHIER_PASSWORD")
    demo_export_accounts_path: str = Field(
        default="../.local-tools/demo/accounts.txt",
        alias="DEMO_EXPORT_ACCOUNTS_PATH",
    )

    # SSE & Rate limit knobs (tunable for fast deterministic tests)
    sse_poll_interval_seconds: float = Field(default=1.0, alias="SSE_POLL_INTERVAL_SECONDS")
    sse_heartbeat_seconds: float = Field(default=15.0, alias="SSE_HEARTBEAT_SECONDS")
    sse_max_connections_per_principal: int = Field(
        default=5, alias="SSE_MAX_CONNECTIONS_PER_PRINCIPAL"
    )
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _validate_dsn(cls, v: str) -> str:
        return normalize_psycopg_dsn(v)

    @field_validator("session_secret")
    @classmethod
    def _validate_secret(cls, v: str) -> str:
        if len(v.strip()) < 32 or v.startswith("REPLACE_WITH_"):
            raise ValueError("SESSION_SECRET must be at least 32 characters and not a placeholder")
        return v

    @field_validator("public_base_url")
    @classmethod
    def _validate_public_base_url(cls, v: str) -> str:
        parsed = urlparse(v.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("PUBLIC_BASE_URL must be a valid http/https origin")
        return v.strip().rstrip("/")

    @model_validator(mode="after")
    def _validate_environment_invariants(self) -> Settings:
        if self.app_env in {"production", "staging"}:
            if self.enable_mocks:
                raise ValueError("ENABLE_MOCKS must be false in staging/production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in staging/production")
        return self

    @property
    def allowed_origins_set(self) -> set[str]:
        return {o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()}

    @property
    def allowed_hosts_set(self) -> set[str]:
        return {h.strip().lower() for h in self.allowed_hosts.split(",") if h.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

