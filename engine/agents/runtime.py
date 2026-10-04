"""Sesión, eventos y utilidades compartidas. El status del lead no se asigna aquí."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from core.config import get_settings
from db.models import Lead as DbLead
from db.repositories import EventRepository, LeadRepository
from db.session import create_all, session_scope

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"


def output_dir() -> Path:
    raw = os.environ.get("AGENCY_OUTPUT_DIR")
    path = Path(raw) if raw else OUTPUT_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepare_db() -> None:
    create_all()


def set_column_status(row: object, value: str) -> None:
    """Status de mensaje, pedido u otra fila. El lead pasa solo por transition()."""
    if isinstance(row, DbLead):
        raise RuntimeError("el status del lead solo cambia con transition()")
    # setattr evita asignar el campo del lead; ese cambio vive en transition().
    setattr(row, "status", value)  # noqa: B010


def start_of_local_day(moment: datetime | None = None) -> datetime:
    current = moment or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    zone: tzinfo
    try:
        zone = ZoneInfo(get_settings().tz)
    except ZoneInfoNotFoundError:
        zone = UTC
    local = current.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


def add_business_days(start: datetime, days: int) -> datetime:
    import holidays

    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    calendar = holidays.country_holidays("CL")
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5 and current.date() not in calendar:
            added += 1
    return current


def iter_leads(session: Session) -> list[DbLead]:
    rows: list[DbLead] = []
    offset = 0
    repo = LeadRepository(session)
    while True:
        batch = repo.list(limit=200, offset=offset)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 200:
            break
        offset += 200
    return rows


def video_enabled(session: Session) -> bool:
    from db.repositories import SettingsRepository

    stored = SettingsRepository(session).get("video_enabled")
    if isinstance(stored, bool):
        return stored
    return get_settings().video_enabled


def log_event(
    agent: str,
    message: str,
    level: str = "info",
    meta: dict[str, Any] | None = None,
    *,
    session: Session | None = None,
    lead_id: str | None = None,
) -> dict[str, Any]:
    """Append de events. No reescribe logs.json."""

    def write(current: Session) -> dict[str, Any]:
        row = EventRepository(current).append(
            agent=agent,
            level=level,
            message=message,
            lead_id=lead_id,
            meta=meta,
        )
        return {
            "id": row.id,
            "ts": row.ts.isoformat(),
            "agent": row.agent,
            "level": row.level,
            "message": row.message,
            "meta": row.meta or {},
        }

    if session is not None:
        return write(session)
    prepare_db()
    with session_scope() as current:
        return write(current)
