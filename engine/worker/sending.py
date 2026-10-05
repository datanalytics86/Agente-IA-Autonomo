"""Envíos, secuencia, opt-out y guardia de tasa. Instagram/LinkedIn/WhatsApp no salen."""

from __future__ import annotations

import json
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from jinja2 import Environment, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.catalog import SAFE_INTENTS
from agents.context import AgentContext
from agents.copy import diagnosis_fallback, register_agent_fallbacks
from agents.diagnoser import DiagnoserAgent
from agents.mobile import MobileAgent
from agents.schemas import DiagnosisOutput
from core.compliance import is_opt_out, looks_like_injection
from core.config import get_settings
from core.hitl import channel_should_pause, needs_value_review
from core.states import TRANSITIONS, transition
from db.models import Lead, Message, new_id
from db.normalize import contact_hash, normalize_contact
from db.repositories import (
    EventRepository,
    LeadRepository,
    MessageRepository,
    SettingsRepository,
    SuppressionRepository,
)
from integrations.email.base import build_transactional_email
from integrations.llm.base import build_llm
from integrations.pagespeed.base import FakeWebAuditor, HttpWebAuditor, WebsiteAudit
from worker.approvals import ensure_approval
from worker.clock import SystemClock
from worker.copywriter import MANUAL_CHANNELS, outreach_parts
from worker.funnel import queue_outbound
from worker.persist import patch_fields
from worker.ports import JobContext
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
from worker.testing_ports import build_default_ports

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
    if isinstance(raw, bool) or not isinstance(raw, int | str):
        return get_settings().email_outreach_daily_limit
    try:
        return int(raw)
    except ValueError:
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


class _Inbound(Protocol):
    @property
    def from_email(self) -> str: ...

    @property
    def body(self) -> str: ...

    @property
    def intent(self) -> str: ...


@dataclass(frozen=True)
class _RoutedMail:
    from_email: str
    body: str
    intent: str = ""
    channel: str = _OUTREACH
    provider_message_id: str | None = None
    received_at: datetime | None = None


class _Auditor(Protocol):
    def audit(self, url: str | None) -> WebsiteAudit: ...


_INFORME_ENV = Environment(autoescape=select_autoescape(["html", "xml"]))
_INFORME_HTML = """<!doctype html>
<html lang="es-CL">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe de presencia web</title>
</head>
<body>
<h1>Informe de presencia web de {{ business }}</h1>
<p>{{ gap_summary }}</p>
{% if opportunities %}
<ul>
{% for item in opportunities %}
<li>{{ item.title }} — {{ item.detail }}</li>
{% endfor %}
</ul>
{% endif %}
<p>Puntaje de oportunidad: {{ score }}.</p>
<p>Paquete sugerido: {{ package }}.</p>
<p><a href="{{ agenda_url }}">Agendar una conversación</a></p>
<p>
Este correo es el informe pedido en el formulario.
No sustituye al aviso de recepción y no es una oferta en frío.
</p>
</body>
</html>
"""
_INFORME_KIND = "informe_diagnostico"
_PRESET_ADVANCE = frozenset(
    {"interesado", "pregunta_precio", "agendar", "fuera_de_oficina", "otro"}
)
_OPEN_SEQUENCE = frozenset({"queued", "approved", "checking", "draft"})


def apply_inbound(ctx: JobContext, mails: Sequence[_Inbound]) -> int:
    """Opt-out determinista primero. Sin intención, clasifica con Mobile."""
    handled = 0
    for mail in mails:
        lead = _lead_for_mail(ctx.session, mail)
        if lead is None:
            continue
        body = mail.body or ""
        given = _given_intent(mail)
        channel = _mail_channel(mail)
        optout = is_opt_out(body) or given == "opt_out"
        injected = given == "prompt_injection" or looks_like_injection(body)
        if optout:
            _store_inbound(
                ctx, lead, body, channel=channel, intent="opt_out", confidence=1.0, mail=mail
            )
            _suppress(ctx, lead, body)
            if _can_go(lead.status, "opt_out"):
                transition(ctx.session, lead, "opt_out", actor="sistema", reason="opt-out")
            handled += 1
            continue
        if injected:
            _store_inbound(
                ctx, lead, body, channel=channel, intent="otro", confidence=1.0, mail=mail
            )
            EventRepository(ctx.session).append(
                agent="inbound_poll",
                level="warn",
                message="inyección ignorada",
                lead_id=lead.id,
                meta={"obeyed": False},
                ts=ctx.clock.now(),
            )
            handled += 1
            continue
        if given:
            _store_inbound(
                ctx, lead, body, channel=channel, intent=given, confidence=None, mail=mail
            )
            _advance_known(ctx, lead, given)
            handled += 1
            continue
        stored = _store_inbound(
            ctx,
            lead,
            body,
            channel=channel,
            intent=None,
            confidence=None,
            mail=mail,
        )
        _classify_with_mobile(ctx, lead.id)
        ctx.session.refresh(stored)
        _maybe_meta_reply(ctx, lead, stored)
        handled += 1
    return handled


def _given_intent(mail: object) -> str:
    raw = getattr(mail, "intent", "")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _mail_channel(mail: object) -> str:
    raw = getattr(mail, "channel", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    return _OUTREACH


def _provider_on(mail: object) -> str | None:
    raw = getattr(mail, "provider_message_id", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _received_at(mail: object, fallback: datetime) -> datetime:
    raw = getattr(mail, "received_at", None)
    if not isinstance(raw, datetime):
        return fallback
    if raw.tzinfo is None:
        return raw.replace(tzinfo=UTC)
    return raw.astimezone(UTC)


def _store_inbound(
    ctx: JobContext,
    lead: Lead,
    body: str,
    *,
    channel: str,
    intent: str | None,
    confidence: float | None,
    mail: object,
) -> Message:
    return MessageRepository(ctx.session).add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="in",
            channel=channel,
            status="received",
            body_text=body,
            intent=intent,
            intent_confidence=confidence,
            provider_message_id=_free_provider_id(ctx.session, _provider_on(mail)),
            created_at=_received_at(mail, ctx.clock.now()),
        )
    )


def _free_provider_id(session: Session, candidate: str | None) -> str | None:
    if not candidate:
        return None
    taken = session.scalar(select(Message.id).where(Message.provider_message_id == candidate))
    if taken is not None:
        return None
    return candidate


def _unique_provider_id(session: Session, candidate: str | None) -> str:
    chosen = candidate.strip() if isinstance(candidate, str) else ""
    if not chosen:
        chosen = f"tx-{new_id()}"
    while (
        session.scalar(select(Message.id).where(Message.provider_message_id == chosen)) is not None
    ):
        chosen = f"tx-{new_id()}"
    return chosen


def _classify_with_mobile(ctx: JobContext, lead_id: str) -> None:
    MobileAgent().run(AgentContext(ctx.session, lead_id=lead_id))


def _advance_known(ctx: JobContext, lead: Lead, intent: str) -> None:
    if lead.status == "enviado" and intent in _PRESET_ADVANCE:
        transition(ctx.session, lead, "respondio", actor="agente", reason=intent)


def _within_24h(now: datetime, received: datetime | None) -> bool:
    if received is None:
        return False
    moment = received if received.tzinfo is not None else received.replace(tzinfo=UTC)
    return now - moment.astimezone(UTC) <= timedelta(hours=24)


def _meta_reply_text(intent: str) -> str:
    if intent == "agendar":
        return "Gracias por escribir. Puedes elegir un horario en el enlace de agenda del sitio."
    if intent == "pregunta_precio":
        return (
            "Gracias por escribir. Los precios publicados están en la página de paquetes del sitio."
        )
    if intent in {"interesado", "pregunta_detalle", "objecion_tiempo"}:
        return "Gracias por escribir. Seguimos por este mismo medio."
    return ""


def _maybe_meta_reply(ctx: JobContext, lead: Lead, message: Message) -> None:
    """Respuesta automática solo en la ventana de 24 h. El frío no se envía."""
    channel = message.channel
    if channel not in {"instagram", "whatsapp"}:
        return
    within = _within_24h(ctx.clock.now(), message.created_at)
    confidence = message.intent_confidence if isinstance(message.intent_confidence, float) else 0.0
    safe = (
        message.intent in SAFE_INTENTS
        and confidence >= get_settings().mobile_autoreply_min_confidence
    )
    if not safe or not within or not ctx.allow_send:
        return
    if SettingsRepository(ctx.session).get("kill_switch", False) is not True:
        return
    text = _meta_reply_text(message.intent or "")
    if not text:
        return
    from integrations.meta import build_meta

    recipient = lead.phone_public if channel == "whatsapp" else lead.instagram_handle
    if not recipient:
        return
    result = build_meta(get_settings()).send_reply(
        recipient,
        text,
        user_initiated=True,
        within_24h=True,
        channel=channel,
    )
    if result.status != "sent":
        return
    MessageRepository(ctx.session).add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="out",
            channel=channel,
            status="sent",
            body_text=text,
            provider_message_id=_unique_provider_id(ctx.session, result.provider_message_id),
            sent_at=ctx.clock.now(),
            created_at=ctx.clock.now(),
        )
    )


def _suppress(ctx: JobContext, lead: Lead, body: str) -> None:
    _remember(ctx, "email", lead.contact_email or "")
    domain = _domain(lead.contact_email or "")
    if domain:
        _remember(ctx, "domain", domain)
    _remember(ctx, "instagram", lead.instagram_handle or "")
    _remember(ctx, "phone", lead.phone_public or "")
    _remember(ctx, "linkedin", lead.linkedin_url or "")
    EventRepository(ctx.session).append(
        agent="inbound_poll",
        level="info",
        message="opt-out aplicado en el mismo tick",
        lead_id=lead.id,
        meta={"excerpt": body[:120]},
        ts=ctx.clock.now(),
    )


def _remember(ctx: JobContext, kind: str, value: str) -> None:
    if not value.strip():
        return
    row = SuppressionRepository(ctx.session).add(kind, value, reason="opt-out", source="inbound")
    patch_fields(ctx.session, row, created_at=ctx.clock.now())


def _lead_by_email(session: Session, email: str) -> Lead | None:
    target = email.strip().lower()
    if not target or "@" not in target:
        return None
    stmt = select(Lead).where(Lead.contact_email == target)
    return session.scalars(stmt).first()


def _lead_by_handle(session: Session, handle: str) -> Lead | None:
    target = normalize_contact("instagram", handle)
    if not target:
        return None
    stmt = select(Lead).where(Lead.instagram_handle.is_not(None))
    for lead in session.scalars(stmt).all():
        current = lead.instagram_handle or ""
        if current and normalize_contact("instagram", current) == target:
            return lead
    return None


def _lead_by_phone(session: Session, phone: str) -> Lead | None:
    if len(re.sub(r"\D", "", phone)) < 8:
        return None
    digest = contact_hash("phone", phone)
    stmt = select(Lead).where(Lead.phone_public.is_not(None))
    for lead in session.scalars(stmt).all():
        current = lead.phone_public or ""
        if current and contact_hash("phone", current) == digest:
            return lead
    return None


def _lead_for_mail(session: Session, mail: _Inbound) -> Lead | None:
    channel = _mail_channel(mail)
    sender = (mail.from_email or "").strip()
    if channel == "instagram":
        return _lead_by_handle(session, sender)
    if channel == "whatsapp":
        return _lead_by_phone(session, sender)
    if "@" in sender:
        return _lead_by_email(session, sender)
    return _lead_by_phone(session, sender) or _lead_by_handle(session, sender)


def _context_for_session(session: Session) -> JobContext:
    settings = get_settings()
    if settings.app_mode == "prod":
        from worker.wiring import build_ports

        ports = build_ports(settings, session)
    else:
        ports = build_default_ports()
    return JobContext(
        session=session,
        clock=SystemClock(),
        rng=random.Random(0),
        ports=ports,
    )


def _json_object(body: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _email_kind(value: str) -> str:
    text = value.strip().lower()
    if "complain" in text:
        return "complained"
    if "bounce" in text:
        return "bounced"
    if "deliver" in text:
        return "delivered"
    return ""


def _recipients(data: dict[str, Any]) -> list[str]:
    raw = data.get("to")
    found: list[str] = []
    if isinstance(raw, str) and raw.strip():
        found.append(raw.strip())
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                found.append(item.strip())
    return found


def _message_by_provider(session: Session, provider_id: str) -> Message | None:
    if not provider_id:
        return None
    return session.scalar(select(Message).where(Message.provider_message_id == provider_id))


def _stop_sequence(session: Session, lead_id: str) -> None:
    stmt = select(Message).where(
        Message.lead_id == lead_id,
        Message.channel == _OUTREACH,
        Message.direction == "out",
        Message.status.in_(tuple(_OPEN_SEQUENCE)),
    )
    for message in session.scalars(stmt).all():
        patch_fields(session, message, status="blocked")


def apply_email_provider_event(session: Session, body: bytes) -> None:
    """Rebote o queja: supresión, mensaje bounced y secuencia detenida."""
    payload = _json_object(body)
    if payload is None:
        return
    kind = _email_kind(str(payload.get("type") or payload.get("event") or ""))
    if not kind:
        return
    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload
    email_id = str(data.get("email_id") or data.get("provider_message_id") or "").strip()
    recipients = _recipients(data)
    message = _message_by_provider(session, email_id)
    lead: Lead | None = None
    if message is not None:
        lead = session.get(Lead, message.lead_id)
    if lead is None:
        for recipient in recipients:
            lead = _lead_by_email(session, recipient)
            if lead is not None:
                break
    if kind == "delivered":
        if message is not None and message.status in {"sent", "queued"}:
            patch_fields(session, message, status="delivered")
        return
    address = recipients[0] if recipients else (lead.contact_email if lead is not None else "")
    if address:
        SuppressionRepository(session).add("email", address, reason=kind, source="email_webhook")
    if message is None and lead is not None:
        session.add(
            Message(
                lead_id=lead.id,
                thread_id=lead.id,
                direction="out",
                channel=_OUTREACH,
                status="bounced",
                body_text="",
                provider_message_id=_free_provider_id(session, email_id or None),
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
    elif message is not None:
        patch_fields(session, message, status="bounced")
    if lead is None:
        return
    _stop_sequence(session, lead.id)
    if _can_go(lead.status, "perdido"):
        reason = "rebote" if kind == "bounced" else "queja"
        transition(session, lead, "perdido", actor="webhook", reason=reason)


def apply_meta_provider_event(session: Session, body: bytes) -> None:
    """IG o WhatsApp entran como mensaje del lead y pasan por apply_inbound."""
    from integrations.meta.base import parse_inbound

    try:
        inbound = parse_inbound(body)
    except ValueError:
        return
    mails = [
        _RoutedMail(
            from_email=item.sender,
            body=item.text,
            intent="",
            channel=item.channel,
            provider_message_id=item.provider_message_id or None,
            received_at=item.timestamp,
        )
        for item in inbound
        if item.channel in {"instagram", "whatsapp"}
    ]
    if not mails:
        return
    apply_inbound(_context_for_session(session), mails)


def job_inbound(ctx: JobContext) -> int:
    return apply_inbound(ctx, ctx.ports.inbound.poll())


def _auditor_for(ctx: JobContext) -> _Auditor:
    current = ctx.ports.auditor
    if isinstance(current, HttpWebAuditor | FakeWebAuditor):
        return current
    settings = get_settings()
    if settings.app_mode == "prod" and not settings.dry_run:
        base = settings.public_base_url.strip() or "http://localhost"
        return HttpWebAuditor(
            user_agent=f"AgenciaBot/1.0 (+{base})",
            pagespeed_key=settings.pagespeed_api_key,
        )
    return FakeWebAuditor()


def _informe_enviado(session: Session, lead_id: str) -> bool:
    for row in MessageRepository(session).list(lead_id=lead_id, limit=30):
        meta = row.check_result
        if (
            row.channel == "email_tx"
            and row.direction == "out"
            and isinstance(meta, dict)
            and meta.get("kind") == _INFORME_KIND
        ):
            return True
    return False


def _diagnosis_dict(raw: object) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    gap = raw.get("gap_summary")
    if not isinstance(gap, str) or not gap.strip():
        return None
    return raw


def _diag_payload(lead: Lead) -> dict[str, Any]:
    settings = get_settings()
    high = bool(lead.high_value or needs_value_review(lead.estimated_value_clp))
    raw_price = lead.estimated_value_clp
    price: int | None = raw_price
    if high or raw_price < 250_000 or raw_price > 450_000:
        price = None
    tone = lead.tone if lead.tone in {"tu", "usted"} else "tu"
    return {
        "lead_id": lead.id,
        "business": lead.business,
        "category": lead.category,
        "commune": lead.commune,
        "city": lead.city,
        "rating": lead.rating,
        "rating_known": lead.rating is not None,
        "reviews": lead.reviews,
        "website_url": lead.website_url,
        "has_website": bool(lead.website_url),
        "opportunity_score": lead.opportunity_score,
        "high_value": high,
        "tone": tone,
        "price_clp": price,
        "agency_name": settings.agency_name,
        "agency_email": settings.agency_email,
        "public_base_url": settings.public_base_url,
    }


def _usable_diagnosis(diag: DiagnosisOutput, data: dict[str, Any]) -> bool:
    if diag.tone != data.get("tone"):
        return False
    for fact in diag.personalization_facts:
        value = data.get(fact.field)
        if value is None or value == "":
            return False
        if str(value) not in fact.text:
            return False
    return True


def _ensure_diagnosis(ctx: JobContext, lead: Lead) -> dict[str, Any]:
    ready = _diagnosis_dict(lead.diagnosis)
    if ready is not None:
        return ready
    if lead.status == "nuevo":
        DiagnoserAgent().run(AgentContext(ctx.session, lead_id=lead.id))
        ctx.session.refresh(lead)
        ready = _diagnosis_dict(lead.diagnosis)
        if ready is not None:
            return ready
    data = _diag_payload(lead)
    register_agent_fallbacks()
    settings = get_settings()
    diag = build_llm(settings, ctx.session).complete_json(
        "diagnoser",
        DiagnosisOutput,
        data,
        model=settings.llm_model,
    )
    if not _usable_diagnosis(diag, data):
        diag = diagnosis_fallback(data)
    stored = diag.model_dump()
    stored["markdown"] = f"### {lead.business}\n\n{diag.gap_summary}\n"
    patch_fields(ctx.session, lead, diagnosis=stored, tone=diag.tone)
    return stored


def _agenda_url(ctx: JobContext, lead_id: str) -> str:
    link = ctx.ports.bookings.link_for(lead_id)
    if link.strip():
        return link
    base = get_settings().public_base_url.rstrip("/") or "http://localhost"
    return f"{base}/agendar?lead_id={lead_id}"


def _opportunity_rows(diagnosis: dict[str, Any]) -> list[dict[str, str]]:
    raw = diagnosis.get("opportunities")
    rows: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        detail = item.get("detail")
        rows.append(
            {
                "title": title if isinstance(title, str) else "",
                "detail": detail if isinstance(detail, str) else "",
            }
        )
    return rows


def _deliver_informe(ctx: JobContext, lead: Lead, diagnosis: dict[str, Any], score: int) -> bool:
    email = lead.contact_email or ""
    if not email:
        return False
    gap = diagnosis.get("gap_summary")
    gap_text = gap if isinstance(gap, str) else ""
    package = diagnosis.get("recommended_package")
    package_label = package if isinstance(package, str) else ""
    agenda = _agenda_url(ctx, lead.id)
    business = lead.business
    html = _INFORME_ENV.from_string(_INFORME_HTML).render(
        business=business,
        gap_summary=gap_text,
        opportunities=_opportunity_rows(diagnosis),
        score=score,
        package=package_label,
        agenda_url=agenda,
    )
    text = (
        f"Informe de presencia web de {business}.\n\n{gap_text}\n\n"
        f"Paquete sugerido: {package_label}.\n"
        f"Agendar una conversación: {agenda}\n"
    )
    subject = f"Informe de presencia web de {business}"
    result = build_transactional_email(get_settings()).send(
        email,
        subject,
        text,
        html,
        {},
        consent=True,
        kind="diagnostico",
    )
    sent = result.status == "sent"
    MessageRepository(ctx.session).add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="out",
            channel="email_tx",
            status="sent" if sent else "failed",
            subject=subject,
            body_text=text,
            body_html=html,
            check_result={_INFORME_KIND: True, "kind": _INFORME_KIND} if sent else None,
            provider_message_id=_unique_provider_id(ctx.session, result.provider_message_id)
            if sent
            else None,
            sent_at=ctx.clock.now() if sent else None,
            created_at=ctx.clock.now(),
        )
    )
    return sent


def job_diagnostico_gratis(ctx: JobContext) -> int:
    """Audita, diagnostica y envía el informe. El aviso «Recibimos» no lo reemplaza."""
    stmt = select(Lead).where(Lead.source == "inbound_diagnostico")
    sent = 0
    auditor = _auditor_for(ctx)
    for lead in list(ctx.session.scalars(stmt).all()):
        if not lead.contact_email or _suppressed(ctx.session, lead):
            continue
        if _informe_enviado(ctx.session, lead.id):
            continue
        audit = auditor.audit(lead.website_url)
        patch_fields(ctx.session, lead, website_audit=audit.model_dump())
        diagnosis = _ensure_diagnosis(ctx, lead)
        if _deliver_informe(ctx, lead, diagnosis, audit.opportunity_score):
            sent += 1
    return sent


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
