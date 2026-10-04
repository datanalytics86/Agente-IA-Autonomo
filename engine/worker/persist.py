"""Actualiza columnas sin asignación `.status` (la reserva core/states.py)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session


def patch_fields(session: Session, row: Any, **fields: Any) -> None:
    model = type(row)
    session.execute(update(model).where(model.id == row.id).values(**fields))
    session.flush()
    session.refresh(row)
