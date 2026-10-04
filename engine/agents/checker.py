"""Checker v2 por mensaje: reglas y juez. El desacuerdo va a HITL."""

from __future__ import annotations

from typing import Any

from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import log_event, set_column_status
from agents.schemas import JudgeVerdict
from core.compliance import check_rules
from core.config import get_settings
from core.states import TRANSITIONS, transition
from db.models import Approval, Message
from db.repositories import ApprovalRepository, LeadRepository, MessageRepository
from integrations.llm.base import LlmClient, build_llm


class CheckerAgent:
    def __init__(self, llm: LlmClient | None = None) -> None:
        self._llm = llm

    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        messages = _targets(ctx)
        checked: list[str] = []
        events: list[str] = []
        for message in messages:
            lead = LeadRepository(ctx.session).get(message.lead_id)
            if lead is None or lead.status == "revision" or lead.high_value:
                continue
            outcome = self._review(ctx, message, lead)
            checked.append(message.id)
            events.append(outcome)
        if checked:
            log_event(
                "Checker",
                f"{len(checked)} mensajes revisados",
                session=ctx.session,
            )
        return AgentResult(
            lead_id=ctx.lead_id,
            ok=True,
            events=events,
            output={"message_ids": checked},
        )

    def _review(self, ctx: AgentContext, message: Message, lead: Any) -> str:
        settings = get_settings()
        layer1 = check_rules(
            {
                "body": message.body_text,
                "body_html": message.body_html or "",
                "channel": message.channel,
                "direction": message.direction,
                "subject": message.subject or "",
            },
            {
                "contact_email": lead.contact_email,
                "phone_public": lead.phone_public,
                "instagram_handle": lead.instagram_handle,
                "linkedin_url": lead.linkedin_url,
                "website_url": lead.website_url,
                "business": lead.business,
            },
            {
                "agency_name": settings.agency_name,
                "price_min_clp": settings.price_min_clp,
                "price_max_clp": settings.price_max_clp,
                "public_base_url": settings.public_base_url,
                "agency_email": settings.agency_email,
            },
        )
        client = self._llm or build_llm(settings, ctx.session)
        verdict = client.complete_json(
            "checker_judge",
            JudgeVerdict,
            {
                "lead_id": lead.id,
                "channel": message.channel,
                "subject": message.subject or "",
                "layer1_approved": layer1.approved,
                "layer1_reasons": layer1.reasons,
                "body_untrusted": message.body_text,
            },
            model=settings.llm_model_fast,
        )
        disagreement = layer1.approved != verdict.approved
        approved = layer1.approved and verdict.approved and not disagreement
        message.check_result = {
            "approved": approved,
            "disagreement": disagreement,
            "layer1": layer1.model_dump(),
            "layer2": verdict.model_dump(),
        }
        if approved:
            set_column_status(message, "approved")
            text = f"mensaje aprobado · {lead.business}"
            log_event("Checker", text, session=ctx.session, lead_id=lead.id)
            return text
        if disagreement:
            reason = "desacuerdo entre reglas y juez"
            kind = "compliance"
        else:
            reason = "la capa de reglas rechazó el mensaje"
            kind = "compliance"
        set_column_status(message, "rejected")
        _hitl(ctx, lead, kind, reason, message.check_result)
        text = f"mensaje a revisión · {lead.business}: {reason}"
        log_event("Checker", text, level="warn", session=ctx.session, lead_id=lead.id)
        return text


def _targets(ctx: AgentContext) -> list[Message]:
    repo = MessageRepository(ctx.session)
    if ctx.message_id:
        message = repo.get(ctx.message_id)
        if message is None or message.status != "checking":
            return []
        return [message]
    if ctx.lead_id:
        rows = repo.list(lead_id=ctx.lead_id, limit=50)
    else:
        rows = repo.list(limit=200)
    return [row for row in rows if row.direction == "out" and row.status == "checking"]


def _hitl(ctx: AgentContext, lead: Any, kind: str, reason: str, payload: dict[str, Any]) -> None:
    ApprovalRepository(ctx.session).add(
        Approval(
            lead_id=lead.id,
            kind=kind,
            payload={"reason": reason, "check_result": payload},
            status="pending",
        )
    )
    if "revision" in TRANSITIONS.get(lead.status, frozenset()):
        transition(ctx.session, lead, "revision", actor="agente", reason=reason)
