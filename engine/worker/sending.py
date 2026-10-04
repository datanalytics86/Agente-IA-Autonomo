"""Envíos, secuencia, opt-out y guardia de tasa. Instagram/LinkedIn/WhatsApp no salen."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.compliance import is_opt_out, looks_like_injection
from core.config import get_settings
from core.hitl import channel_should_pause, needs_value_review
from core.states import TRANSITIONS, transition
from db.models import Lead, Message
from db.repositories import (
    EventRepository,
    LeadRepository,
    MessageRepository,
    SettingsRepository,
    SuppressionRepository,
)
from worker.approvals import ensure_approval
from worker.copywriter import MANUAL_CHANNELS, outreach_parts
from worker.funnel import queue_outbound
from worker.persist import patch_fields
from worker.ports import InboundMail, JobContext
from worker.schedule import (
    add_business_days,
    after_jitter,
    in_send_window,
    is_business_day,
    jitter_minutes,
    local_date,
    next_window_open,
    start_of_local_day,
)

_OUTREACH = "email_outreach"
_SENT = ("sent", "delivered", "bounced")
_STOP_STATUSES = frozenset(
    {
        "opt_out",
        "perdido",
        "revision",
        "respondio",
        "agendado",
        "propuesta",
        "pagado",
        "en_produccion",
        "en_revision_cliente",
        "entregado",
        "postventa",
    }
)


def _quotas(session: Session) -> dict[str, object]:
    raw = SettingsRepository(session).get("quotas")
    return dict(raw) if isinstance(raw, dict) else {}


def daily_limit(session: Session) -> int:
    quotas = _quotas(session)
    raw = quotas.get("email_outreach_daily_limit")
    if raw is None:
        return get_settings().email_outreach_daily_limit
    try:
        return int(raw)
    except (TypeError, ValueError):
        return get_settings().email_outreach_daily_limit


def _save_next(ctx: JobContext, moment: datetime) -> None:
    SettingsRepository(ctx.session).put(
        "next_outreach_at",
        moment.isoformat(),
        updated_by="outreach_send",
    )


def _defer(ctx: JobContext, minutes: int) -> None:
    candidate = ctx.clock.now() + timedelta(minutes=minutes)
    if in_send_window(candidate):
        _save_next(ctx, candidate)
        return
    _save_next(ctx, next_window_open(candidate))


def channel_paused(session: Session, channel: str) -> bool:
    raw = SettingsRepository(session).get("channel_paused")
    return isinstance(raw, dict) and raw.get(channel) is True


def _domain(email: str) -> str:
    if "@" not in email:
        return ""
    return email.split("@", 1)[1].lower().strip()


def _sent_today(session: Session, now: datetime) -> list[Message]:
    start = start_of_local_day(now)
    end = start + timedelta(days=1)
    stmt = select(Message).where(
        Message.channel == _OUTREACH,
        Message.status.in_(_SENT),
        Message.sent_at >= start,
        Message.sent_at < end,
    )
    return list(session.scalars(stmt).all())


def _suppressed(session: Session, lead: Lead) -> bool:
    repo = SuppressionRepository(session)
    email = lead.contact_email or ""
    if email and repo.contains("email", email):
        return True
    domain = _domain(email)
    if domain and repo.contains("domain", domain):
        return True
    return False


def _stopped(session: Session, lead: Lead) -> bool:
    if lead.status in _STOP_STATUSES:
        return True
    if _suppressed(session, lead):
        return True
    rows = MessageRepository(session).list(lead_id=lead.id, limit=50)
    if any(row.direction == "in" for row in rows):
        return True
    if any(row.status == "bounced" for row in rows):
        return True
    return False


def _can_go(status: str, target: str) -> bool:
    if status == "revision":
        return target in {"perdido", "opt_out"}
    return target in TRANSITIONS.get(status, frozenset())


def job_outreach(ctx: JobContext) -> int:
    _normalize_manual(ctx)
    if not ctx.allow_send:
        _defer(ctx, 30)
        return 0
    if channel_paused(ctx.session, _OUTREACH) or not in_send_window(ctx.clock.now()):
        _defer(ctx, 30)
        return 0
    today = _sent_today(ctx.session, ctx.clock.now())
    if len(today) >= daily_limit(ctx.session):
        _defer(ctx, 30)
        return 0
    used_domains = {_domain(_recipient(ctx.session, item)) for item in today}
    due = MessageRepository(ctx.session).claim_due(now=ctx.clock.now(), limit=50)
    due.sort(key=lambda item: (item.scheduled_at or ctx.clock.now(), item.id))
    for message in due:
        if message.channel in MANUAL_CHANNELS:
            patch_fields(ctx.session, message, status="manual_pending")
            continue
        if message.channel != _OUTREACH or message.direction != "out":
            continue
        if not _approved(message):
            patch_fields(ctx.session, message, status="rejected")
            continue
        lead = LeadRepository(ctx.session).get(message.lead_id)
        if lead is None or not lead.contact_email:
            patch_fields(ctx.session, message, status="blocked")
            continue
        if _blocked_lead(ctx, lead, message):
            continue
        domain = _domain(lead.contact_email)
        if domain and domain in used_domains:
            continue
        result = ctx.ports.outreach.send(
            message.id,
            lead.contact_email,
            message.subject or "",
            message.body_text,
            message.body_html or "",
        )
        if result.status == "bounced":
            patch_fields(
                ctx.session,
                message,
                status="bounced",
                sent_at=ctx.clock.now(),
                provider_message_id=result.provider_message_id,
            )
            if _can_go(lead.status, "perdido"):
                transition(ctx.session, lead, "perdido", actor="sistema", reason="rebote")
        elif result.status == "sent":
            patch_fields(
                ctx.session,
                message,
                status="sent",
                sent_at=ctx.clock.now(),
                provider_message_id=result.provider_message_id,
            )
            if lead.status == "pitch_listo":
                transition(
                    ctx.session,
                    lead,
                    "enviado",
                    actor="agente",
                    reason="outreach enviado",
                    checker_approved=True,
                )
        else:
            patch_fields(ctx.session, message, status="blocked")
            _defer(ctx, 5)
            return 0
        EventRepository(ctx.session).append(
            agent="outreach_send",
            level="info",
            message=f"{result.status} {lead.contact_email}",
            lead_id=lead.id,
            ts=ctx.clock.now(),
        )
        minutes = jitter_minutes(ctx.rng, real=ctx.clock.is_real)
        _save_next(ctx, after_jitter(ctx.clock.now(), minutes))
        return 1
    _defer(ctx, 5)
    return 0


def _recipient(session: Session, message: Message) -> str:
    lead = LeadRepository(session).get(message.lead_id)
    if lead is None or not lead.contact_email:
        return ""
    return lead.contact_email


def _approved(message: Message) -> bool:
    result = message.check_result
    return isinstance(result, dict) and result.get("approved") is True


def _blocked_lead(ctx: JobContext, lead: Lead, message: Message) -> bool:
    if needs_value_review(lead.estimated_value_clp) or lead.high_value:
        if _can_go(lead.status, "revision"):
            transition(ctx.session, lead, "revision", actor="agente", reason="deal alto valor")
            ensure_approval(
                ctx.session,
                lead_id=lead.id,
                kind="deal_alto_valor",
                payload={"estimated_value_clp": lead.estimated_value_clp},
            )
        patch_fields(ctx.session, message, status="blocked")
        return True
    if lead.status in {"opt_out", "perdido", "revision"} or _suppressed(ctx.session, lead):
        patch_fields(ctx.session, message, status="blocked")
        return True
    if _stopped(ctx.session, lead) and (message.sequence_step or 1) > 1:
        patch_fields(ctx.session, message, status="blocked")
        return True
    if lead.status not in {"pitch_listo", "enviado"}:
        patch_fields(ctx.session, message, status="blocked")
        return True
    return False


def _normalize_manual(ctx: JobContext) -> None:
    stmt = select(Message).where(
        Message.channel.in_(tuple(MANUAL_CHANNELS)),
        Message.direction == "out",
        Message.status.in_(("queued", "approved", "checking", "sent", "delivered")),
    )
    for message in ctx.session.scalars(stmt).all():
        if message.status in {"sent", "delivered"}:
            patch_fields(ctx.session, message, status="manual_pending", sent_at=None)
        else:
            patch_fields(ctx.session, message, status="manual_pending")


def apply_inbound(ctx: JobContext, mails: list[InboundMail]) -> int:
    """Opt-out determinista en el mismo tick, antes de cualquier envío."""
    handled = 0
    for mail in mails:
        lead = _lead_by_email(ctx.session, mail.from_email)
        if lead is None:
            continue
        injected = mail.intent == "prompt_injection" or looks_like_injection(mail.body)
        optout = is_opt_out(mail.body) or mail.intent == "opt_out"
        intent = "opt_out" if optout and not injected else mail.intent
        if injected and not optout:
            intent = "otro"
        MessageRepository(ctx.session).add(
            Message(
                lead_id=lead.id,
                thread_id=lead.id,
                direction="in",
                channel=_OUTREACH,
                status="received",
                body_text=mail.body,
                intent=intent,
                created_at=ctx.clock.now(),
            )
        )
        handled += 1
        if optout:
            _suppress(ctx, lead, mail.body)
            if _can_go(lead.status, "opt_out"):
                transition(ctx.session, lead, "opt_out", actor="sistema", reason="opt-out")
            continue
        if injected:
            EventRepository(ctx.session).append(
                agent="inbound_poll",
                level="warn",
                message="inyección ignorada",
                lead_id=lead.id,
                meta={"obeyed": False},
                ts=ctx.clock.now(),
            )
            continue
        if lead.status == "enviado" and mail.intent in {
            "interesado",
            "pregunta_precio",
            "agendar",
            "fuera_de_oficina",
            "otro",
        }:
            transition(
                ctx.session,
                lead,
                "respondio",
                actor="agente",
                reason=mail.intent,
            )
    return handled


def _suppress(ctx: JobContext, lead: Lead, body: str) -> None:
    repo = SuppressionRepository(ctx.session)
    email = lead.contact_email or ""
    if email:
        row = repo.add("email", email, reason="opt-out", source="inbound")
        patch_fields(ctx.session, row, created_at=ctx.clock.now())
        domain = _domain(email)
        if domain:
            domain_row = repo.add("domain", domain, reason="opt-out", source="inbound")
            patch_fields(ctx.session, domain_row, created_at=ctx.clock.now())
    EventRepository(ctx.session).append(
        agent="inbound_poll",
        level="info",
        message="opt-out aplicado en el mismo tick",
        lead_id=lead.id,
        meta={"excerpt": body[:120]},
        ts=ctx.clock.now(),
    )


def _lead_by_email(session: Session, email: str) -> Lead | None:
    target = email.strip().lower()
    stmt = select(Lead).where(Lead.contact_email == target)
    return session.scalars(stmt).first()


def job_inbound(ctx: JobContext) -> int:
    return apply_inbound(ctx, ctx.ports.inbound.poll())


def job_followups(ctx: JobContext) -> int:
    settings = get_settings()
    today = local_date(ctx.clock.now())
    steps = (
        (2, settings.followup_1_business_days),
        (3, settings.followup_2_business_days),
    )
    stmt = select(Message).where(
        Message.channel == _OUTREACH,
        Message.direction == "out",
        Message.sequence_step == 1,
        Message.status.in_(("sent", "delivered")),
    )
    created = 0
    for first in ctx.session.scalars(stmt).all():
        if first.sent_at is None:
            continue
        lead = LeadRepository(ctx.session).get(first.lead_id)
        if lead is None or _stopped(ctx.session, lead):
            continue
        existing = MessageRepository(ctx.session).list(lead_id=lead.id, limit=20)
        have = {item.sequence_step for item in existing}
        sent_day = local_date(first.sent_at)
        for step, days in steps:
            if step in have:
                continue
            if today < add_business_days(sent_day, days):
                continue
            scheduled = ctx.clock.now()
            if not in_send_window(scheduled):
                scheduled = next_window_open(scheduled)
            subject, text, body_html = outreach_parts(
                business=lead.business,
                commune=lead.commune,
                step=step,
            )
            queue_outbound(
                ctx,
                lead,
                channel=_OUTREACH,
                subject=subject,
                text=text,
                body_html=body_html,
                step=step,
                scheduled=scheduled,
            )
            created += 1
    return created


def job_response_guard(ctx: JobContext) -> int:
    if channel_paused(ctx.session, _OUTREACH):
        return 0
    sent_rows = list(
        ctx.session.scalars(
            select(Message).where(
                Message.channel == _OUTREACH,
                Message.direction == "out",
                Message.status.in_(_SENT),
            )
        ).all()
    )
    if not sent_rows:
        return 0
    sent_ids = {row.lead_id for row in sent_rows}
    inbound = list(
        ctx.session.scalars(
            select(Message).where(Message.direction == "in", Message.channel == _OUTREACH)
        ).all()
    )
    responded = {row.lead_id for row in inbound if row.lead_id in sent_ids}
    sent_n = len(sent_rows)
    resp_n = len(responded)
    if not channel_should_pause(_OUTREACH, sent_n, resp_n, session=ctx.session):
        return 0
    current = SettingsRepository(ctx.session).get("channel_paused")
    paused = dict(current) if isinstance(current, dict) else {}
    paused[_OUTREACH] = True
    SettingsRepository(ctx.session).put("channel_paused", paused, updated_by="response_rate_guard")
    rate = resp_n / sent_n if sent_n else 0.0
    ensure_approval(
        ctx.session,
        lead_id=sent_rows[0].lead_id,
        kind="tasa_respuesta_baja",
        payload={
            "channel": _OUTREACH,
            "sent": sent_n,
            "responded": resp_n,
            "rate": rate,
        },
    )
    EventRepository(ctx.session).append(
        agent="response_rate_guard",
        level="warn",
        message="canal email_outreach pausado por tasa de respuesta",
        lead_id=sent_rows[0].lead_id,
        meta={"sent": sent_n, "responded": resp_n, "rate": rate},
        ts=ctx.clock.now(),
    )
    return 1


def job_warmup(ctx: JobContext) -> int:
    local = local_date(ctx.clock.now())
    if local.weekday() != 0 or not is_business_day(local):
        return 0
    quotas = _quotas(ctx.session)
    if quotas.get("last_ramp_date") == local.isoformat():
        return 0
    current = daily_limit(ctx.session)
    cap = get_settings().email_outreach_daily_max
    updated = min(cap, current + 5)
    quotas["email_outreach_daily_limit"] = updated
    quotas["last_ramp_date"] = local.isoformat()
    SettingsRepository(ctx.session).put("quotas", quotas, updated_by="warmup_ramp")
    return 1 if updated >= current else 0
