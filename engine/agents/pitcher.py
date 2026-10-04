"""Pitcher: un solo canal, sin red. El envío real lo hace el adaptador de A5."""

from __future__ import annotations

import html

from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import add_business_days, log_event, set_column_status
from core.config import get_settings
from core.states import transition
from db.models import Message, utcnow
from db.repositories import LeadRepository, MessageRepository


def choose_channel(lead: object) -> tuple[str, bool]:
    """Email si hay correo público con fuente. Si no, un solo canal manual."""
    email = getattr(lead, "contact_email", None)
    source = getattr(lead, "contact_email_source_url", None)
    if email and source:
        return "email_outreach", False
    if getattr(lead, "instagram_handle", None):
        return "instagram", True
    return "linkedin", True


def ensure_draft(ctx: AgentContext) -> Message | None:
    """Crea un único borrador en `checking`. No envía y no abre sockets."""
    if not ctx.lead_id:
        return None
    lead = LeadRepository(ctx.session).get(ctx.lead_id)
    if lead is None or lead.status != "pitch_listo" or lead.high_value:
        return None
    repo = MessageRepository(ctx.session)
    existing = [
        item
        for item in repo.list(lead_id=lead.id, limit=20)
        if item.direction == "out" and item.sequence_step == 1
    ]
    if existing:
        return existing[0]
    diagnosis = lead.diagnosis if isinstance(lead.diagnosis, dict) else {}
    body = diagnosis.get("pitch_body") if isinstance(diagnosis.get("pitch_body"), str) else ""
    subject = (
        diagnosis.get("pitch_subject") if isinstance(diagnosis.get("pitch_subject"), str) else ""
    )
    if not body.strip():
        return None
    channel, _manual = choose_channel(lead)
    return repo.add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="out",
            channel=channel,
            sequence_step=1,
            status="checking",
            subject=subject,
            body_text=body,
            body_html=f"<p>{html.escape(body)}</p>",
        )
    )


class PitcherAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        if not ctx.lead_id:
            return AgentResult(lead_id=None, ok=False, events=["sin lead"], output={})
        lead = LeadRepository(ctx.session).get(ctx.lead_id)
        if lead is None:
            return AgentResult(
                lead_id=ctx.lead_id, ok=False, events=["lead inexistente"], output={}
            )
        if lead.high_value or lead.status == "revision":
            message = f"sin envío · {lead.business} en revisión"
            log_event("Pitcher", message, level="warn", session=ctx.session, lead_id=lead.id)
            return AgentResult(lead_id=lead.id, ok=True, events=[message], output={"sent": False})
        if lead.status != "pitch_listo":
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})

        repo = MessageRepository(ctx.session)
        approved = [
            item
            for item in repo.list(lead_id=lead.id, limit=20)
            if item.direction == "out" and item.sequence_step == 1 and item.status == "approved"
        ]
        if not approved:
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"sent": False})
        message = approved[0]
        # Un lead, un canal. No se crean los otros.
        siblings = [
            item
            for item in repo.list(lead_id=lead.id, limit=20)
            if item.direction == "out" and item.id != message.id and item.sequence_step == 1
        ]
        for extra in siblings:
            set_column_status(extra, "blocked")

        settings = get_settings()
        if message.channel == "whatsapp":
            set_column_status(message, "blocked")
            log_event(
                "Pitcher",
                f"whatsapp en frío bloqueado · {lead.business}",
                level="error",
                session=ctx.session,
                lead_id=lead.id,
            )
            return AgentResult(
                lead_id=lead.id, ok=True, events=["whatsapp bloqueado"], output={"sent": False}
            )

        if message.channel == "email_outreach":
            if settings.app_mode == "demo" or settings.dry_run:
                set_column_status(message, "sent")
                message.sent_at = utcnow()
                note = f"envío simulado · {lead.business} · email"
                log_event(
                    "Pitcher", note, session=ctx.session, lead_id=lead.id, meta={"simulated": True}
                )
                transition(
                    ctx.session,
                    lead,
                    "enviado",
                    actor="agente",
                    reason="envío simulado de email en demo",
                    checker_approved=True,
                )
                _schedule(ctx, lead)
                return AgentResult(
                    lead_id=lead.id,
                    ok=True,
                    events=[note],
                    output={"sent": True, "channel": "email_outreach"},
                )
            set_column_status(message, "queued")
            note = f"email en cola · {lead.business}"
            log_event("Pitcher", note, session=ctx.session, lead_id=lead.id)
            _schedule(ctx, lead)
            return AgentResult(
                lead_id=lead.id,
                ok=True,
                events=[note],
                output={"sent": False, "channel": "email_outreach"},
            )

        set_column_status(message, "manual_pending")
        manual = _manual_hint(lead, message.channel, message.body_text)
        current = dict(message.check_result or {})
        current["manual"] = manual
        message.check_result = current
        note = f"cola manual · {lead.business} · {message.channel}"
        log_event("Pitcher", note, session=ctx.session, lead_id=lead.id, meta=manual)
        return AgentResult(
            lead_id=lead.id,
            ok=True,
            events=[note],
            output={"sent": False, "channel": message.channel, "manual": True},
        )


def _schedule(ctx: AgentContext, lead: object) -> None:
    settings = get_settings()
    when = add_business_days(utcnow(), settings.followup_1_business_days)
    lead.next_action_at = when
    LeadRepository(ctx.session).save(lead)  # type: ignore[arg-type]


def _manual_hint(lead: object, channel: str, body: str) -> dict[str, str]:
    if channel == "instagram" and getattr(lead, "instagram_handle", None):
        handle = str(lead.instagram_handle)
        return {"profile_url": f"https://instagram.com/{handle}", "copy": body}
    if channel == "linkedin" and getattr(lead, "linkedin_url", None):
        return {"profile_url": str(lead.linkedin_url), "copy": body}
    return {"profile_url": "", "copy": body}
