"""Approvals idempotentes. El lead_id es obligatorio en el esquema."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from db.models import Approval
from db.repositories import ApprovalRepository


def ensure_approval(
    session: Session,
    *,
    lead_id: str,
    kind: str,
    payload: dict[str, Any],
) -> Approval:
    rows = ApprovalRepository(session).list(status="pending", limit=500)
    for row in rows:
        if row.kind != kind:
            continue
        if kind == "tasa_respuesta_baja":
            return row
        if row.lead_id == lead_id:
            return row
    return ApprovalRepository(session).add(
        Approval(lead_id=lead_id, kind=kind, payload=payload, status="pending")
    )
