"""Reporter: un digest por corrida, sin enviar correo."""

from __future__ import annotations

from agents.base import LeadStatus
from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import iter_leads, log_event
from agents.schemas import DailyDigest
from core.config import get_settings
from db.repositories import ApprovalRepository, LlmCallRepository
from integrations.llm.base import build_llm


class ReporterAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        counts: dict[str, int] = {item.value: 0 for item in LeadStatus}
        for lead in iter_leads(ctx.session):
            counts[lead.status] = counts.get(lead.status, 0) + 1
        pending = len(ApprovalRepository(ctx.session).list(status="pending", limit=500))
        spend = float(LlmCallRepository(ctx.session).spend_today_usd())
        settings = get_settings()
        digest = build_llm(settings, ctx.session).complete_json(
            "reporter",
            DailyDigest,
            {
                "leads_by_status": counts,
                "pending_approvals": pending,
                "llm_spend_usd": spend,
            },
        )
        log_event("Reporter", digest.summary, session=ctx.session)
        return AgentResult(
            lead_id=None, ok=True, events=[digest.summary], output=digest.model_dump()
        )
