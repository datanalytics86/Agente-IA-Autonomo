"""Diagnoser: JSON fundamentado y alto valor a revisión."""

from __future__ import annotations

import re

from agents.catalog import TONE_BY_CATEGORY
from agents.context import AgentContext, AgentResult
from agents.copy import diagnosis_fallback, register_agent_fallbacks
from agents.runtime import log_event
from agents.schemas import DiagnosisOutput
from core.config import get_settings
from core.hitl import needs_value_review
from core.states import transition
from db.models import Approval
from db.repositories import ApprovalRepository, LeadRepository
from integrations.llm.base import build_llm

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_FIELDS = {
    "business",
    "category",
    "commune",
    "city",
    "rating",
    "reviews",
    "website_url",
    "opportunity_score",
}


class DiagnoserAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        if not ctx.lead_id:
            return AgentResult(lead_id=None, ok=False, events=["sin lead"], output={})
        lead = LeadRepository(ctx.session).get(ctx.lead_id)
        if lead is None:
            return AgentResult(
                lead_id=ctx.lead_id, ok=False, events=["lead inexistente"], output={}
            )
        if lead.status != "nuevo":
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})

        settings = get_settings()
        data = _payload(lead, settings.agency_name, settings.public_base_url, settings.agency_email)
        diag = build_llm(settings, ctx.session).complete_json(
            "diagnoser",
            DiagnosisOutput,
            data,
            model=settings.llm_model,
        )
        if not _grounded(diag, data):
            diag = diagnosis_fallback(data)
            log_event(
                "Diagnoser",
                f"diagnóstico de {lead.business} volvió al template: hechos no fundamentados",
                level="warn",
                session=ctx.session,
                lead_id=lead.id,
            )
        stored = diag.model_dump()
        stored["markdown"] = f"### {lead.business}\n\n{diag.gap_summary}\n"
        lead.diagnosis = stored
        lead.tone = diag.tone
        LeadRepository(ctx.session).save(lead)
        high = bool(lead.high_value or needs_value_review(lead.estimated_value_clp))
        if high:
            _ensure_approval(ctx, lead.id, lead.estimated_value_clp, lead.category)
            transition(
                ctx.session,
                lead,
                "revision",
                actor="agente",
                reason="deal de alto valor: revisión humana antes de enviar",
            )
            level = "warn"
        else:
            transition(
                ctx.session,
                lead,
                "diagnosticado",
                actor="agente",
                reason="diagnóstico listo",
            )
            level = "info"
        message = f"diagnóstico listo · {lead.business} → {lead.status}"
        log_event("Diagnoser", message, level=level, session=ctx.session, lead_id=lead.id)
        return AgentResult(
            lead_id=lead.id,
            ok=True,
            events=[message],
            output=diag.model_dump(),
        )


def _payload(
    lead: object, agency_name: str, public_base_url: str, agency_email: str
) -> dict[str, object]:
    rating = getattr(lead, "rating", None)
    reviews = getattr(lead, "reviews", None)
    high = bool(getattr(lead, "high_value", False) or needs_value_review(lead.estimated_value_clp))
    price = lead.estimated_value_clp
    if high or not isinstance(price, int) or price < 250_000 or price > 450_000:
        price_out: int | None = None
    else:
        price_out = price
    audit = getattr(lead, "website_audit", None)
    html = ""
    if isinstance(audit, dict):
        raw = audit.get("html") or audit.get("page_html") or ""
        html = raw if isinstance(raw, str) else ""
    category = str(lead.category)
    return {
        "lead_id": lead.id,
        "business": lead.business,
        "category": category,
        "commune": lead.commune,
        "city": lead.city,
        "rating": rating,
        "rating_known": rating is not None,
        "reviews": reviews,
        "website_url": lead.website_url,
        "has_website": bool(lead.website_url),
        "opportunity_score": lead.opportunity_score,
        "high_value": high,
        "tone": TONE_BY_CATEGORY.get(category, "tu"),
        "price_clp": price_out,
        "agency_name": agency_name,
        "agency_email": agency_email,
        "public_base_url": public_base_url,
        "page_html_untrusted": html,
    }


def _grounded(diag: DiagnosisOutput, data: dict[str, object]) -> bool:
    if diag.tone != data.get("tone"):
        return False
    for fact in diag.personalization_facts:
        if fact.field not in _FIELDS:
            return False
        value = data.get(fact.field)
        if value is None or value == "":
            return False
        if str(value) not in fact.text:
            return False
    for found in _EMAIL_RE.findall(diag.pitch_body):
        allowed = str(data.get("agency_email") or "").lower()
        if found.lower() != allowed:
            return False
    return True


def _ensure_approval(ctx: AgentContext, lead_id: str, value: int, category: str) -> None:
    repo = ApprovalRepository(ctx.session)
    for row in repo.list(status="pending", limit=200):
        if row.lead_id == lead_id and row.kind == "deal_alto_valor":
            return
    repo.add(
        Approval(
            lead_id=lead_id,
            kind="deal_alto_valor",
            payload={"estimated_value_clp": value, "category": category},
            status="pending",
        )
    )
