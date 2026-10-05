"""Scout y avance de embudo. El tick invoca los mismos agentes que el demo."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.builder import BuilderAgent
from agents.checker import CheckerAgent
from agents.closer import CloserAgent
from agents.context import AgentContext
from agents.delivery import DeliveryAgent
from agents.diagnoser import DiagnoserAgent
from agents.filmer import FilmerAgent
from agents.mobile import MobileAgent
from agents.pitcher import PitcherAgent, ensure_draft
from agents.reporter import ReporterAgent
from core.compliance import check_rules
from core.config import get_settings
from core.errors import DuplicateLeadError
from core.hitl import needs_value_review
from core.states import transition
from db.models import Lead, Message
from db.repositories import (
    EventRepository,
    LeadRepository,
    LlmCallRepository,
    MessageRepository,
    OrderRepository,
    SettingsRepository,
)
from worker.approvals import ensure_approval
from worker.copywriter import checker_settings, outreach_parts
from worker.persist import patch_fields
from worker.ports import JobContext, PlaceHit
from worker.schedule import in_send_window, local_date, next_window_open

_CHAINS = ("mcdonald", "starbucks", "burger king", "kfc", "subway", "papa john")
_USTED = frozenset({"clinica-dental", "optica", "abogados", "estudio-contable"})
_ACTIVE = frozenset(
    {
        "nuevo",
        "diagnosticado",
        "revision",
        "landing",
        "video",
        "pitch_listo",
        "respondio",
        "agendado",
        "propuesta",
        "pagado",
        "en_produccion",
        "en_revision_cliente",
    }
)


def _counter(session: Session, key: str) -> int:
    raw = SettingsRepository(session).get(key, 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _put_counter(session: Session, key: str, value: int, *, who: str) -> None:
    SettingsRepository(session).put(key, value, updated_by=who)


def _is_chain(name: str) -> bool:
    folded = name.casefold()
    return any(token in folded for token in _CHAINS)


def _compliance_settings() -> dict[str, object]:
    return checker_settings()


def _lead_view(lead: Lead) -> dict[str, object]:
    return {
        "contact_email": lead.contact_email,
        "phone_public": lead.phone_public,
        "instagram_handle": lead.instagram_handle,
        "linkedin_url": lead.linkedin_url,
        "website_url": lead.website_url,
        "business": lead.business,
    }


def job_scout(ctx: JobContext) -> int:
    settings = get_settings()
    day = local_date(ctx.clock.now()).isoformat()
    key = f"scout_count:{day}"
    already = _counter(ctx.session, key)
    if already >= settings.scout_daily_limit:
        return 0
    communes = settings.scout_commune_list or ["Providencia"]
    categories = settings.scout_category_list or ["cafeteria"]
    cursor = SettingsRepository(ctx.session).get("scout_cursor") or {}
    if not isinstance(cursor, dict):
        cursor = {}
    commune_i = int(cursor.get("commune") or 0)
    category_i = int(cursor.get("category") or 0)
    commune = communes[commune_i % len(communes)]
    category = categories[category_i % len(categories)]
    room = settings.scout_daily_limit - already
    hits = ctx.ports.places.search(commune, category, room)
    known = {
        lead.place_id for lead in LeadRepository(ctx.session).list(limit=5000) if lead.place_id
    }
    created = 0
    for hit in hits:
        if created >= room:
            break
        if not _accept_hit(hit, settings.scout_min_rating, settings.scout_min_reviews):
            continue
        if hit.place_id in known:
            continue
        lead = _lead_from_hit(ctx, hit)
        try:
            LeadRepository(ctx.session).add(lead)
        except DuplicateLeadError:
            continue
        known.add(hit.place_id)
        created += 1
        if needs_value_review(lead.estimated_value_clp):
            transition(
                ctx.session,
                lead,
                "revision",
                actor="agente",
                reason="deal alto valor",
            )
            ensure_approval(
                ctx.session,
                lead_id=lead.id,
                kind="deal_alto_valor",
                payload={"estimated_value_clp": lead.estimated_value_clp},
            )
    _put_counter(ctx.session, key, already + created, who="scout")
    SettingsRepository(ctx.session).put(
        "scout_cursor",
        {"commune": commune_i + 1, "category": category_i + 1},
        updated_by="scout",
    )
    return created


def _accept_hit(hit: PlaceHit, min_rating: float, min_reviews: int) -> bool:
    if hit.business_status != "OPERATIONAL":
        return False
    if _is_chain(hit.name):
        return False
    if (hit.rating or 0) < min_rating:
        return False
    if (hit.user_rating_count or 0) < min_reviews:
        return False
    if not 0 <= hit.opportunity_score <= 100:
        return False
    return True


def _lead_from_hit(ctx: JobContext, hit: PlaceHit) -> Lead:
    high = needs_value_review(hit.estimated_value_clp)
    return Lead(
        id=f"lead_{hit.place_id}",
        source="outbound_demo",
        business=hit.name,
        category=hit.category,
        city=hit.city,
        commune=hit.commune,
        address_public=hit.formatted_address,
        place_id=hit.place_id,
        website_url=hit.website_uri,
        website_audit={"scenario": hit.scenario, "raw": hit.unsafe_text},
        opportunity_score=hit.opportunity_score,
        rating=hit.rating,
        reviews=hit.user_rating_count,
        contact_email=hit.email,
        instagram_handle=hit.instagram_handle,
        linkedin_url=hit.linkedin_url,
        phone_public=hit.phone_public,
        status="nuevo",
        estimated_value_clp=hit.estimated_value_clp,
        high_value=high,
        tone="usted" if hit.category in _USTED else "tu",
        created_at=ctx.clock.now(),
        updated_at=ctx.clock.now(),
    )


@dataclass
class _Tick:
    moved: int = 0
    diagnosed: int = 0


def job_pipeline(ctx: JobContext) -> int:
    """Una pasada por lead, en el mismo orden que Orchestrator._advance."""
    settings = get_settings()
    day = local_date(ctx.clock.now()).isoformat()
    key = f"diagnose_count:{day}"
    already = _counter(ctx.session, key)
    room = settings.diagnose_daily_limit - already
    seen: set[str] = set()
    moved = 0
    diagnosed = 0
    rows = list(
        ctx.session.scalars(
            select(Lead)
            .where(Lead.status.in_(_ACTIVE), Lead.source != "sistema")
            .order_by(Lead.opportunity_score.desc(), Lead.business.asc(), Lead.id.asc())
        ).all()
    )
    for lead in rows:
        tick = _advance(ctx, lead.id, room - diagnosed, seen)
        moved += tick.moved
        diagnosed += tick.diagnosed
    if diagnosed:
        _put_counter(ctx.session, key, already + diagnosed, who="pipeline_tick")
    MobileAgent().run(AgentContext(ctx.session))
    if _budget_open(ctx, "reporter", None, seen):
        ReporterAgent().run(AgentContext(ctx.session))
    return moved


def _budget_open(ctx: JobContext, agent: str, lead_id: str | None, seen: set[str]) -> bool:
    spent = LlmCallRepository(ctx.session).spend_today_usd(now=ctx.clock.now())
    limit = Decimal(str(get_settings().llm_daily_budget_usd))
    if spent < limit:
        return True
    if agent not in seen:
        seen.add(agent)
        EventRepository(ctx.session).append(
            agent="pipeline",
            level="warn",
            message="presupuesto LLM del día agotado",
            lead_id=lead_id,
            ts=ctx.clock.now(),
        )
    return False


def _reload(ctx: JobContext, lead_id: str, current: Lead) -> Lead:
    fresh = LeadRepository(ctx.session).get(lead_id)
    return fresh if fresh is not None else current


def _finish(ctx: JobContext, lead_id: str, before: str, diagnosed: int) -> _Tick:
    lead = LeadRepository(ctx.session).get(lead_id)
    moved = 1 if lead is not None and lead.status != before else 0
    return _Tick(moved=moved, diagnosed=diagnosed)


def _advance(ctx: JobContext, lead_id: str, room: int, seen: set[str]) -> _Tick:
    repo = LeadRepository(ctx.session)
    lead = repo.get(lead_id)
    if lead is None or lead.status not in _ACTIVE:
        return _Tick()
    before = lead.status
    diagnosed = 0
    agent_ctx = AgentContext(ctx.session, lead_id=lead_id)
    if lead.status == "nuevo":
        if room <= 0 or not _budget_open(ctx, "diagnoser", lead.id, seen):
            return _Tick()
        DiagnoserAgent().run(agent_ctx)
        lead = _reload(ctx, lead_id, lead)
        if lead.status != "nuevo":
            diagnosed = 1
    if lead.status in {"diagnosticado", "revision"}:
        if not _budget_open(ctx, "builder", lead.id, seen):
            return _finish(ctx, lead_id, before, diagnosed)
        BuilderAgent().run(agent_ctx)
        lead = _reload(ctx, lead_id, lead)
    if lead.status in {"landing", "revision"}:
        if not _budget_open(ctx, "filmer", lead.id, seen):
            return _finish(ctx, lead_id, before, diagnosed)
        FilmerAgent().run(agent_ctx)
        lead = _reload(ctx, lead_id, lead)
    if lead.high_value or lead.status == "revision":
        return _finish(ctx, lead_id, before, diagnosed)
    if lead.status == "pitch_listo":
        _pitch(ctx, lead, agent_ctx, seen)
        lead = _reload(ctx, lead_id, lead)
    if lead.status in {"agendado", "respondio"}:
        if not _budget_open(ctx, "closer", lead.id, seen):
            return _finish(ctx, lead_id, before, diagnosed)
        CloserAgent().run(agent_ctx)
        _attach_deposit(ctx, lead.id)
        lead = _reload(ctx, lead_id, lead)
    if lead.status == "pagado":
        if not _budget_open(ctx, "delivery", lead.id, seen):
            return _finish(ctx, lead_id, before, diagnosed)
        DeliveryAgent().run(agent_ctx)
        lead = _reload(ctx, lead_id, lead)
    if lead.status in {"en_produccion", "en_revision_cliente"}:
        if _budget_open(ctx, "builder", lead.id, seen):
            BuilderAgent().run(agent_ctx)
    return _finish(ctx, lead_id, before, diagnosed)


def _pitch(ctx: JobContext, lead: Lead, agent_ctx: AgentContext, seen: set[str]) -> None:
    if not in_send_window(ctx.clock.now()):
        lead.next_action_at = next_window_open(ctx.clock.now())
        LeadRepository(ctx.session).save(lead)
        return
    _fill_pitch_fallback(ctx, lead)
    ensure_draft(agent_ctx)
    if not _budget_open(ctx, "checker", lead.id, seen):
        return
    CheckerAgent().run(agent_ctx)
    PitcherAgent().run(agent_ctx)
    _stamp_schedule(ctx, lead.id)


def _fill_pitch_fallback(ctx: JobContext, lead: Lead) -> None:
    raw = lead.diagnosis
    diagnosis: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    body = diagnosis.get("pitch_body")
    if isinstance(body, str) and body.strip():
        return
    subject, text, _html = outreach_parts(
        business=lead.business,
        commune=lead.commune,
        step=1,
    )
    diagnosis["pitch_subject"] = subject
    diagnosis["pitch_body"] = text
    diagnosis["pitch_source"] = "copywriter"
    lead.diagnosis = diagnosis
    LeadRepository(ctx.session).save(lead)


def _stamp_schedule(ctx: JobContext, lead_id: str) -> None:
    when = ctx.clock.now()
    if not in_send_window(when):
        when = next_window_open(when)
    for message in MessageRepository(ctx.session).list(lead_id=lead_id, limit=20):
        if message.direction != "out" or message.sequence_step != 1:
            continue
        if message.status == "queued" and message.scheduled_at is None:
            patch_fields(ctx.session, message, scheduled_at=when)


def _preference_is_local() -> bool:
    settings = get_settings()
    return bool(
        settings.app_mode == "demo" or settings.dry_run or not settings.mp_access_token.strip()
    )


def _attach_deposit(ctx: JobContext, lead_id: str) -> None:
    if not _preference_is_local():
        return
    orders = OrderRepository(ctx.session).list(lead_id=lead_id, limit=5)
    if not orders or orders[0].checkout_url:
        return
    order = orders[0]
    deposit = order.total_clp * order.deposit_percent // 100
    amount = deposit if deposit > 0 else order.total_clp
    lead = LeadRepository(ctx.session).get(lead_id)
    business = lead.business if lead is not None else lead_id
    pref = ctx.ports.payments.create_preference(order.id, f"Anticipo {business}", amount)
    patch_fields(
        ctx.session,
        order,
        checkout_url=pref.url,
        provider_preference_id=pref.preference_id,
    )


def _review(
    ctx: JobContext,
    lead: Lead,
    channel: str,
    subject: str,
    text: str,
    body_html: str,
) -> dict[str, object]:
    message = {
        "body": text,
        "body_html": body_html,
        "channel": channel,
        "direction": "out",
        "subject": subject,
        "suppressed": False,
        "recipient_suppressed": False,
    }
    view = _lead_view(lead)
    rules = check_rules(message, view, _compliance_settings())
    judge = ctx.ports.judge.review(message, view)
    approved = bool(rules.approved and judge.approved)
    result: dict[str, object] = {
        "approved": approved,
        "rules": rules.model_dump(),
        "judge": judge.model_dump(),
    }
    if rules.approved != judge.approved:
        ensure_approval(
            ctx.session,
            lead_id=lead.id,
            kind="compliance",
            payload={"reason": "desacuerdo reglas/juez", "channel": channel},
        )
    return result


def queue_outbound(
    ctx: JobContext,
    lead: Lead,
    *,
    channel: str,
    subject: str,
    text: str,
    body_html: str,
    step: int,
    scheduled: object,
) -> None:
    result = _review(ctx, lead, channel, subject, text, body_html)
    status = "queued" if result["approved"] is True else "rejected"
    MessageRepository(ctx.session).add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="out",
            channel=channel,
            sequence_step=step,
            status=status,
            subject=subject,
            body_text=text,
            body_html=body_html,
            check_result=result,
            scheduled_at=scheduled,
            created_at=ctx.clock.now(),
        )
    )
