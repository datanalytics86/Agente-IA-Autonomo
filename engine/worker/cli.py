"""Arranque del worker. Si el lock está tomado, sale 0."""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime

from db.session import create_all, session_scope
from worker.locking import acquire_lock
from worker.scheduler import build_scheduler


def main() -> int:
    create_all()
    owner = f"{socket.gethostname()}:{os.getpid()}"
    with session_scope() as session:
        if not acquire_lock(session, owner, datetime.now(UTC)):
            print("Otra instancia del worker está activa; salgo sin tomar el lock.")
            return 0
    scheduler = build_scheduler(owner)
    scheduler.start()
    return 0
