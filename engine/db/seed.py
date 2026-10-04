"""Siembra el kill switch detenido. Una segunda corrida no lo duplica ni lo pisa."""

from __future__ import annotations

from db.models import Setting
from db.repositories import SettingsRepository
from db.session import create_all, reset_engine, session_scope


def main() -> int:
    create_all()
    try:
        with session_scope() as session:
            current = session.get(Setting, "kill_switch")
            if current is None:
                SettingsRepository(session).put("kill_switch", False, updated_by="seed")
                print("seed: kill_switch=false")
            else:
                print("seed: kill_switch ya existe")
    finally:
        reset_engine()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
