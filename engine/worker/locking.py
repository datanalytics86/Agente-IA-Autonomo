"""Lock de fila única. Si el heartbeat tiene más de 60 s, otra instancia lo toma."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db.models import WorkerLock

LOCK_ID = 1
LOCK_TTL = timedelta(seconds=60)


def acquire_lock(session: Session, owner: str, now: datetime) -> bool:
    row = session.get(WorkerLock, LOCK_ID)
    if row is None:
        session.add(WorkerLock(id=LOCK_ID, owner=owner, heartbeat_at=now))
        session.flush()
        return True
    if row.owner == owner or now - row.heartbeat_at > LOCK_TTL:
        row.owner = owner
        row.heartbeat_at = now
        session.flush()
        return True
    return False


def refresh_lock(session: Session, owner: str, now: datetime) -> bool:
    """Renueva el heartbeat. False si otra instancia viva es la dueña."""
    row = session.get(WorkerLock, LOCK_ID)
    if row is None:
        return acquire_lock(session, owner, now)
    if row.owner != owner and now - row.heartbeat_at <= LOCK_TTL:
        return False
    row.owner = owner
    row.heartbeat_at = now
    session.flush()
    return True
