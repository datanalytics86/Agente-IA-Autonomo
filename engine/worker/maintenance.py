"""Digest, retención, vencimientos, métricas y postventa."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.states import transition
from db.models import Artifact, Lead, Message, Payment
from db.repositories import (
    ApprovalRepository,
    DataRequestRepository,
    EventRepository,
    ProjectRepository,
    SettingsRepository,
)
from worker.ports import JobContext
from worker.schedule import local_date

_QUIET = frozenset({"nuevo", "diagnosticado", "perdido"})


def job_digest(ctx: JobContext) -> int:
    pending = ApprovalRepository(ctx.session).list(status="pending", limit=500)
    lines = [f"{row.kind} lead={row.lead_id}" for row in pending]
    text = "\n".join(lines) if lines else "sin approvals pendientes"
    ctx.ports.notifier.send_digest(text)
    EventRepository(ctx.session).append(
        agent="hitl_digest",
        level="info",
        message=f"digest: {len(pending)} approvals pendientes",
        meta={"count": len(pending)},
        ts=ctx.clock.now(),
    )
    return len(pending)


def job_demo_expiry(ctx: JobContext) -> int:
    now = ctx.clock.now()
    rows = list(
        ctx.session.scalars(
            select(Artifact).where(
                Artifact.kind == "landing_demo",
                Artifact.expires_at.is_not(None),
                Artifact.expires_at <= now,
            )
        ).all()
    )
    expired = 0
    for artifact in rows:
        meta = dict(artifact.meta or {})
        if meta.get("expired") is True:
            continue
        meta["expired"] = True
        artifact.meta = meta
        expired += 1
    return expired


def job_retention(ctx: JobContext) -> int:
    cutoff = ctx.clock.now() - timedelta(days=get_settings().retention_days)
    rows = list(
        ctx.session.scalars(
            select(Lead).where(
                Lead.anonymized_at.is_(None),
                Lead.created_at < cutoff,
                Lead.status.in_(tuple(_QUIET)),
                Lead.source != "sistema",
            )
        ).all()
    )
    done = 0
    for lead in rows:
        interacted = ctx.session.scalar(
            select(func.count()).select_from(Message).where(Message.lead_id == lead.id)
        )
        if interacted:
            continue
        lead.contact_email = None
        lead.contact_email_source_url = None
        lead.instagram_handle = None
        lead.linkedin_url = None
        lead.phone_public = None
        lead.address_public = None
        lead.website_url = None
        lead.business = f"Anonimo {lead.id[:8]}"
        lead.diagnosis = None
        lead.website_audit = None
        lead.anonymized_at = ctx.clock.now()
        done += 1
    if done:
        ctx.session.flush()
    return done


def job_data_requests(ctx: JobContext) -> int:
    horizon = ctx.clock.now() + timedelta(days=3)
    warned = 0
    for request in DataRequestRepository(ctx.session).list(status="open", limit=200):
        if request.due_at > horizon:
            continue
        EventRepository(ctx.session).append(
            agent="data_requests_watch",
            level="warn",
            message=f"solicitud {request.kind} de {request.requester_email} vence pronto",
            meta={"request_id": request.id, "due_at": request.due_at.isoformat()},
            ts=ctx.clock.now(),
        )
        warned += 1
    return warned


def job_metrics(ctx: JobContext) -> int:
    counts = _status_counts(ctx.session)
    sent = ctx.session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.channel == "email_outreach", Message.status.in_(("sent", "delivered")))
    )
    revenue = ctx.session.scalar(select(func.coalesce(func.sum(Payment.amount_clp), 0)))
    paused = SettingsRepository(ctx.session).get("channel_paused")
    payload = {
        "date": local_date(ctx.clock.now()).isoformat(),
        "by_status": counts,
        "sent": int(sent or 0),
        "revenue_clp": int(revenue or 0),
        "paused_channels": sorted(key for key, value in paused.items() if value)
        if isinstance(paused, dict)
        else [],
    }
    SettingsRepository(ctx.session).put("metrics_latest", payload, updated_by="metrics_rollup")
    EventRepository(ctx.session).append(
        agent="metrics_rollup",
        level="info",
        message="métricas consolidadas",
        meta=payload,
        ts=ctx.clock.now(),
    )
    return 1


def _status_counts(session: Session) -> dict[str, int]:
    rows = session.execute(select(Lead.status, func.count()).group_by(Lead.status)).all()
    return {str(status): int(count) for status, count in rows}


def job_postventa(ctx: JobContext) -> int:
    cutoff = ctx.clock.now() - timedelta(days=30)
    leads = list(ctx.session.scalars(select(Lead).where(Lead.status == "entregado")).all())
    moved = 0
    for lead in leads:
        projects = ProjectRepository(ctx.session).list(lead_id=lead.id, limit=3)
        if not projects or projects[0].delivered_at is None:
            continue
        if projects[0].delivered_at > cutoff:
            continue
        transition(ctx.session, lead, "postventa", actor="agente", reason="30 días de entregado")
        EventRepository(ctx.session).append(
            agent="postventa",
            level="info",
            message="postventa a 30 días",
            lead_id=lead.id,
            ts=ctx.clock.now(),
        )
        moved += 1
    return moved
