"""Closer: propuesta y orden. Sin token de pago no llama a la red."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agents.catalog import PACKAGE_CLP
from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import ROOT, log_event, output_dir
from agents.schemas import ProposalOutput
from core.config import get_settings
from core.hitl import needs_value_review
from core.states import TRANSITIONS, transition
from db.models import Approval, Artifact, Order, new_id
from db.repositories import (
    ApprovalRepository,
    ArtifactRepository,
    LeadRepository,
    MessageRepository,
    OrderRepository,
)
from integrations.llm.base import build_llm

_REVISIONS = {"landing_esencial": 1, "landing_pro": 2, "landing_premium": 3, "multi_sede": 1}


class CloserAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        if not ctx.lead_id:
            return AgentResult(lead_id=None, ok=True, events=[], output={"skipped": True})
        lead = LeadRepository(ctx.session).get(ctx.lead_id)
        if lead is None or lead.status not in {"agendado", "respondio"}:
            return AgentResult(lead_id=ctx.lead_id, ok=True, events=[], output={"skipped": True})
        if lead.status == "respondio" and not _wants_to_buy(ctx, lead.id):
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})
        if OrderRepository(ctx.session).list(lead_id=lead.id, limit=5):
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})
        if lead.high_value or needs_value_review(lead.estimated_value_clp):
            _approval(
                ctx, lead.id, "deal_alto_valor", "el cierre supera la banda y queda en revisión"
            )
            if "revision" in TRANSITIONS.get(lead.status, frozenset()):
                transition(
                    ctx.session, lead, "revision", actor="agente", reason="cierre de alto valor"
                )
            return AgentResult(
                lead_id=lead.id, ok=True, events=["alto valor"], output={"sent": False}
            )

        package = _package(lead.diagnosis)
        amount = PACKAGE_CLP.get(package)
        if amount is None:
            _approval(ctx, lead.id, "fuera_de_alcance", "paquete sin precio publicado")
            return AgentResult(
                lead_id=lead.id, ok=True, events=["sin precio"], output={"sent": False}
            )

        settings = get_settings()
        proposal = build_llm(settings, ctx.session).complete_json(
            "closer",
            ProposalOutput,
            {
                "lead_id": lead.id,
                "business": lead.business,
                "price_clp": amount,
                "revisions": _REVISIONS.get(package, 1),
                "deposit_percent": settings.deposit_percent,
                "includes_iva": settings.prices_include_iva,
            },
        )
        net, iva, total = _money(amount, settings.prices_include_iva)
        order = OrderRepository(ctx.session).add(
            Order(
                lead_id=lead.id,
                package_code=package,
                amount_clp=net,
                iva_clp=iva,
                total_clp=total,
                deposit_percent=settings.deposit_percent,
                status="pending",
                checkout_url=None,
            )
        )
        path = _write(lead.business, lead.commune, proposal)
        ArtifactRepository(ctx.session).add(
            Artifact(
                lead_id=lead.id,
                kind="propuesta",
                path=str(path),
                public_token=new_id(),
                meta={"order_id": order.id, "package": package},
            )
        )
        transition(ctx.session, lead, "propuesta", actor="agente", reason="propuesta emitida")
        log_event(
            "Closer",
            f"propuesta sin cobro en línea · {lead.business}",
            level="warn",
            session=ctx.session,
            lead_id=lead.id,
        )
        return AgentResult(
            lead_id=lead.id, ok=True, events=["propuesta"], output={"order_id": order.id}
        )


def _package(diagnosis: object) -> str:
    if isinstance(diagnosis, dict):
        raw = diagnosis.get("recommended_package")
        if isinstance(raw, str) and raw in PACKAGE_CLP:
            return raw
    return "landing_esencial"


def _wants_to_buy(ctx: AgentContext, lead_id: str) -> bool:
    for message in MessageRepository(ctx.session).list(lead_id=lead_id, limit=30):
        if message.direction == "in" and message.intent in {"interesado", "agendar"}:
            return True
    return False


def _money(amount: int, include_iva: bool) -> tuple[int, int, int]:
    if include_iva:
        total = amount
        net = int(round(total / 1.19))
        return net, total - net, total
    iva = int(round(amount * 0.19))
    return amount, iva, amount + iva


def _write(business: str, commune: str, proposal: ProposalOutput) -> Path:
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates" / "proposals"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    html = env.get_template("propuesta.html").render(
        title=proposal.title,
        business=business,
        commune=commune,
        scope=proposal.scope,
        timeline=proposal.timeline,
        revisions=proposal.revisions,
        price_label=f"{proposal.price_clp:,}".replace(",", "."),
        includes_iva=proposal.includes_iva,
        deposit_percent=proposal.deposit_percent,
    )
    path = output_dir() / f"propuesta-{new_id()[:8]}.html"
    path.write_text(html, encoding="utf-8")
    return path


def _approval(ctx: AgentContext, lead_id: str, kind: str, reason: str) -> None:
    ApprovalRepository(ctx.session).add(
        Approval(lead_id=lead_id, kind=kind, payload={"reason": reason}, status="pending")
    )
