"""Engine y sesiones. SQLite usa BEGIN IMMEDIATE y check_same_thread=False."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from core.config import get_settings
from db.models import Base

_engine: Engine | None = None
_engine_url: str | None = None


def _sqlite_on_connect(dbapi_connection: Any, _connection_record: Any) -> None:
    # Autocommit del driver: el BEGIN lo emite SQLAlchemy y nosotros lo hacemos IMMEDIATE.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def _sqlite_on_begin(connection: Connection) -> None:
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def _prepare_sqlite(engine: Engine) -> None:
    event.listen(engine, "connect", _sqlite_on_connect)
    event.listen(engine, "begin", _sqlite_on_begin)


def get_engine(url: str | None = None) -> Engine:
    global _engine, _engine_url
    db_url = url or get_settings().database_url
    if _engine is not None and _engine_url == db_url:
        return _engine
    reset_engine()
    kwargs: dict[str, Any] = {"poolclass": NullPool}
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(db_url, **kwargs)
    if engine.dialect.name == "sqlite":
        _prepare_sqlite(engine)
    _engine = engine
    _engine_url = db_url
    return engine


def reset_engine() -> None:
    global _engine, _engine_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    current = Session(engine or get_engine(), expire_on_commit=False)
    try:
        yield current
        current.commit()
    except Exception:
        current.rollback()
        raise
    finally:
        current.close()


def create_all(engine: Engine | None = None) -> None:
    Base.metadata.create_all(engine or get_engine())
