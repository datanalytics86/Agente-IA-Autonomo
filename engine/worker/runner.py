"""Envoltura de jobs: job_runs, kill switch, reintentos y dead-letter."""

from __future__ import annotations

import time
from collections.abc import Callable

from core.config import get_settings
from core.errors import DuplicateLeadError
from db.models import Approval, Lead
from db.repositories import (
    ApprovalRepository,
    EventRepository,
    JobRunRepository,
    LeadRepository,
    SettingsRepository,
)
from worker.ports import JobContext

SENDING_JOBS = frozenset({"outreach_send"})
SYSTEM_LEAD_ID = "lead_sistema"


def execute(name: str, fn: Callable[[JobContext], int], ctx: JobContext) -> int:
    """Abre job_runs, reintenta con backoff y tras 3 fallos crea error_sistema."""
    session = ctx.session
    runs = JobRunRepository(session)
    run = runs.start(name)
    attempts = max(1, get_settings().job_max_retries)
    kill = SettingsRepository(session).get("kill_switch", False) is True
    ctx.allow_send = kill if name in SENDING_JOBS else True
    if name in SENDING_JOBS and not kill:
        EventRepository(session).append(
            agent=name,
            level="info",
            message="kill switch detenido; no se envía",
            ts=ctx.clock.now(),
        )

    error: Exception | None = None
    processed = 0
    for attempt in range(1, attempts + 1):
        try:
            with session.begin_nested():
                processed = fn(ctx)
            error = None
            break
        except Exception as exc:
            error = exc
            if attempt < attempts and ctx.clock.is_real:
                time.sleep(2 ** (attempt - 1))
    if error is not None:
        runs.finish(run, status="error", processed=0, error=str(error)[:500])
        _error_approval(ctx, name, error)
        return 0
    runs.finish(run, status="ok", processed=processed)
    return processed


def _error_approval(ctx: JobContext, name: str, error: Exception) -> None:
    lead_id = getattr(error, "lead_id", None)
    if not isinstance(lead_id, str) or not lead_id:
        lead_id = _system_lead(ctx).id
    payload = {"job": name, "error": str(error)[:500]}
    existing = ApprovalRepository(ctx.session).list(status="pending", limit=500)
    for row in existing:
        if row.kind == "error_sistema" and row.lead_id == lead_id:
            current = row.payload if isinstance(row.payload, dict) else {}
            if current.get("job") == name and current.get("error") == payload["error"]:
                return
    ApprovalRepository(ctx.session).add(
        Approval(
            lead_id=lead_id,
            kind="error_sistema",
            payload=payload,
            status="pending",
        )
    )
    EventRepository(ctx.session).append(
        agent=name,
        level="error",
        message=f"job {name} agotó reintentos",
        lead_id=lead_id,
        meta=payload,
        ts=ctx.clock.now(),
    )


def _system_lead(ctx: JobContext) -> Lead:
    repo = LeadRepository(ctx.session)
    found = repo.get(SYSTEM_LEAD_ID)
    if found is not None:
        return found
    lead = Lead(
        id=SYSTEM_LEAD_ID,
        source="sistema",
        business="Sistema interno",
        category="ferreteria",
        city="Santiago",
        commune="Interna",
        opportunity_score=0,
        status="nuevo",
        estimated_value_clp=0,
        high_value=False,
        tone="tu",
        created_at=ctx.clock.now(),
        updated_at=ctx.clock.now(),
    )
    try:
        return repo.add(lead)
    except DuplicateLeadError:
        again = repo.get(SYSTEM_LEAD_ID)
        if again is None:
            raise
        return again
