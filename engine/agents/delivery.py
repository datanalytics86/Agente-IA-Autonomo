"""Delivery: portal de intake. No envía correo ni abre sockets."""

from __future__ import annotations

from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import log_event
from agents.schemas import DeliveryNote
from core.config import get_settings
from core.states import transition
from db.models import Project, new_id
from db.repositories import LeadRepository, OrderRepository, ProjectRepository
from integrations.llm.base import build_llm

_REVISIONS = {"landing_esencial": 1, "landing_pro": 2, "landing_premium": 3}


class DeliveryAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        if not ctx.lead_id:
            return AgentResult(lead_id=None, ok=True, events=[], output={"skipped": True})
        lead = LeadRepository(ctx.session).get(ctx.lead_id)
        if lead is None or lead.status != "pagado":
            return AgentResult(lead_id=ctx.lead_id, ok=True, events=[], output={"skipped": True})
        if ProjectRepository(ctx.session).list(lead_id=lead.id, limit=5):
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})
        orders = OrderRepository(ctx.session).list(lead_id=lead.id, limit=5)
        if not orders:
            log_event(
                "Delivery",
                f"sin orden para producir · {lead.business}",
                level="warn",
                session=ctx.session,
                lead_id=lead.id,
            )
            return AgentResult(lead_id=lead.id, ok=False, events=["sin orden"], output={})

        settings = get_settings()
        portal_token = new_id()
        project = ProjectRepository(ctx.session).add(
            Project(
                order_id=orders[0].id,
                lead_id=lead.id,
                status="intake_pendiente",
                revisions_used=0,
                max_revisions=_REVISIONS.get(orders[0].package_code, 1),
                portal_token=portal_token,
            )
        )
        portal = f"/proyecto/{portal_token}"
        note = build_llm(settings, ctx.session).complete_json(
            "delivery",
            DeliveryNote,
            {"lead_id": lead.id, "portal_path": portal, "business": lead.business},
        )
        transition(
            ctx.session,
            lead,
            "en_produccion",
            actor="agente",
            reason="portal de intake listo",
        )
        log_event(
            "Delivery",
            f"intake {note.portal_path} · {lead.business}",
            session=ctx.session,
            lead_id=lead.id,
        )
        return AgentResult(
            lead_id=lead.id,
            ok=True,
            events=[note.summary],
            output={"portal_path": note.portal_path, "project_id": project.id},
        )
