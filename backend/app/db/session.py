"""Database engine, session factory, REPEATABLE READ snapshot helper, and error mapping."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from psycopg import errors as pg_errors
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.errors import AppError

_engines: dict[str, Engine] = {}
_session_factories: dict[str, sessionmaker[Session]] = {}


def get_engine(dsn: str | None = None) -> Engine:
    target_dsn = dsn or get_settings().database_url
    if target_dsn not in _engines:
        engine = create_engine(
            target_dsn,
            pool_size=10,
            max_overflow=10,
            pool_timeout=5,
            pool_pre_ping=True,
            isolation_level="READ COMMITTED",
        )

        @event.listens_for(engine, "connect")
        def _set_session_timeouts(dbapi_connection: Any, _connection_record: Any) -> None:
            with dbapi_connection.cursor() as cur:
                cur.execute("SET lock_timeout = '5000ms'")
                cur.execute("SET statement_timeout = '5000ms'")
                cur.execute("SET timezone = 'UTC'")

        _engines[target_dsn] = engine
    return _engines[target_dsn]


def get_session_factory(dsn: str | None = None) -> sessionmaker[Session]:
    target_dsn = dsn or get_settings().database_url
    if target_dsn not in _session_factories:
        _session_factories[target_dsn] = sessionmaker(
            bind=get_engine(target_dsn),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _session_factories[target_dsn]


def dispose_engines() -> None:
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
    _session_factories.clear()


def translate_db_operational_error(exc: OperationalError) -> AppError:
    orig = getattr(exc, "orig", None)
    if isinstance(
        orig,
        (
            pg_errors.LockNotAvailable,
            pg_errors.DeadlockDetected,
            pg_errors.SerializationFailure,
            pg_errors.QueryCanceled,
        ),
    ):
        return AppError(
            status_code=503,
            code="RETRYABLE_CONFLICT",
            message="Hệ thống đang xử lý thao tác đồng thời. Vui lòng thử lại cùng mã lệnh.",
            details={"reason": type(orig).__name__},
        )
    return AppError(
        status_code=503,
        code="SERVICE_UNAVAILABLE",
        message="Cơ sở dữ liệu tạm thời không sẵn sàng.",
        details={},
    )


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    except OperationalError as exc:
        session.rollback()
        raise translate_db_operational_error(exc) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def repeatable_read_snapshot(session: Session) -> Generator[Session, None, None]:
    """Execute read-only queries under a single REPEATABLE READ transaction snapshot."""
    try:
        if session.in_transaction():
            session.rollback()
        session.connection(
            execution_options={"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}
        )
        yield session
        session.rollback()
    except OperationalError as exc:
        session.rollback()
        raise translate_db_operational_error(exc) from exc
    except Exception:
        session.rollback()
        raise


def read_event_watermark(session: Session) -> int:
    val = session.execute(text("SELECT last_id FROM event_clock WHERE id = 1")).scalar_one()
    return int(val)

