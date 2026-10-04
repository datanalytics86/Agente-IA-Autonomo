"""Mobile: solo actúa cuando entra un mensaje nuevo."""

from __future__ import annotations

from agents.catalog import SAFE_INTENTS
from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import iter_leads, log_event
from agents.schemas import MobileIntent
from core.compliance import is_opt_out
from core.config import get_settings
from core.states import TRANSITIONS, transition
from db.models import Approval, Lead, Message
from db.repositories import (
    ApprovalRepository,
    LeadRepository,
    MessageRepository,
    SuppressionRepository,
)
from integrations.llm.base import build_llm


class MobileAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        pending = _new_inbound(ctx)
        if not pending:
            return AgentResult(lead_id=ctx.lead_id, ok=True, events=[], output={"processed": 0})

        settings = get_settings()
        events: list[str] = []
        for lead_id, message in pending:
            lead = LeadRepository(ctx.session).get(lead_id)
            if lead is None:
                continue
            if is_opt_out(message.body_text):
                verdict = MobileIntent(
                    intent="opt_out", confidence=1.0, reasons=["opt-out determinista"]
                )
            else:
                verdict = build_llm(settings, ctx.session).complete_json(
                    "mobile_classifier",
                    MobileIntent,
                    {
                        "lead_id": lead.id,
                        "deterministic_intent": None,
                        "inbound_untrusted": message.body_text,
                    },
                    model=settings.llm_model_fast,
                )
            message.intent = verdict.intent
            message.intent_confidence = verdict.confidence
            if verdict.intent == "opt_out":
                _suppress(ctx, lead)
                if "opt_out" in TRANSITIONS.get(lead.status, frozenset()):
                    transition(
                        ctx.session, lead, "opt_out", actor="agente", reason="opt-out del prospecto"
                    )
                text = f"opt-out · {lead.business}"
                log_event("Mobile", text, session=ctx.session, lead_id=lead.id)
                events.append(text)
                continue

            safe = (
                verdict.intent in SAFE_INTENTS
                and verdict.confidence >= settings.mobile_autoreply_min_confidence
            )
            if not safe:
                ApprovalRepository(ctx.session).add(
                    Approval(
                        lead_id=lead.id,
                        kind="baja_confianza",
                        payload={
                            "intent": verdict.intent,
                            "confidence": verdict.confidence,
                            "message_id": message.id,
                        },
                        status="pending",
                    )
                )
                text = f"borrador HITL · {lead.business} · {verdict.intent}"
                log_event("Mobile", text, session=ctx.session, lead_id=lead.id)
                events.append(text)
                continue

            text = f"respuesta lista · {lead.business} · {verdict.intent}"
            log_event("Mobile", text, session=ctx.session, lead_id=lead.id)
            events.append(text)
            _advance(ctx, lead, verdict.intent)
        return AgentResult(
            lead_id=ctx.lead_id,
            ok=True,
            events=events,
            output={"processed": len(events)},
        )


def _new_inbound(ctx: AgentContext) -> list[tuple[str, Message]]:
    repo = MessageRepository(ctx.session)
    if ctx.lead_id:
        leads = [lead for lead in [LeadRepository(ctx.session).get(ctx.lead_id)] if lead]
    else:
        leads = iter_leads(ctx.session)
    found: list[tuple[str, Message]] = []
    for lead in leads:
        for message in repo.list(lead_id=lead.id, limit=50):
            if (
                message.direction == "in"
                and message.status == "received"
                and message.intent is None
            ):
                found.append((lead.id, message))
    return found


def _suppress(ctx: AgentContext, lead: object) -> None:
    repo = SuppressionRepository(ctx.session)
    email = getattr(lead, "contact_email", None)
    handle = getattr(lead, "instagram_handle", None)
    phone = getattr(lead, "phone_public", None)
    linkedin = getattr(lead, "linkedin_url", None)
    if email:
        repo.add("email", str(email), reason="opt-out", source="mobile")
    if handle:
        repo.add("instagram", str(handle), reason="opt-out", source="mobile")
    if phone:
        repo.add("phone", str(phone), reason="opt-out", source="mobile")
    if linkedin:
        repo.add("linkedin", str(linkedin), reason="opt-out", source="mobile")


def _advance(ctx: AgentContext, lead: Lead, intent: str) -> None:
    status = str(lead.status)
    if intent == "agendar" and status in {"enviado", "respondio"}:
        target = "agendado"
    elif status == "enviado":
        target = "respondio"
    else:
        return
    if target not in TRANSITIONS.get(status, frozenset()):
        return
    transition(ctx.session, lead, target, actor="agente", reason=f"intención {intent}")
