"""Scout y avance de embudo. Un paso de estado por lead y por tick."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.compliance import check_rules
from core.config import get_settings
from core.errors import DuplicateLeadError
from core.hitl import needs_value_review
from core.states import transition
from db.models import Artifact, Lead, LlmCall, Message, Order, Payment, Project
from db.repositories import (
    ArtifactRepository,
    EventRepository,
    LeadRepository,
    LlmCallRepository,
    MessageRepository,
    OrderRepository,
    PaymentRepository,
    ProjectRepository,
    SettingsRepository,
)
from worker.approvals import ensure_approval
from worker.copywriter import MANUAL_CHANNELS, checker_settings, offer_price_clp, outreach_parts
from worker.persist import patch_fields
from worker.ports import JobContext, PlaceHit
from worker.schedule import local_date, next_window_open

_CHAINS = ("mcdonald", "starbucks", "burger king", "kfc", "subway", "papa john")
_USTED = frozenset({"clinica-dental", "optica", "abogados", "estudio-contable"})
_PIPELINE_STATUSES = (
    "diagnosticado",
    "landing",
    "video",
    "pitch_listo",
    "respondio",
    "agendado",
    "propuesta",
    "pagado",
    "en_produccion",
    "en_revision_cliente",
)
_PACKAGE = {
    "code": "landing_pro",
    "revisions": 2,
}


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


def _video_enabled(session: Session) -> bool:
    stored = SettingsRepository(session).get("video_enabled")
    if isinstance(stored, bool):
        return stored
    return get_settings().video_enabled


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
        lead.place_id
        for lead in LeadRepository(ctx.session).list(limit=5000)
        if lead.place_id
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


def job_pipeline(ctx: JobContext) -> int:
    diagnosed: set[str] = set()
    moved = _diagnose(ctx, diagnosed)
    rows = list(
        ctx.session.scalars(
            select(Lead)
            .where(Lead.status.in_(_PIPELINE_STATUSES), Lead.source != "sistema")
            .order_by(Lead.opportunity_score.desc(), Lead.business.asc(), Lead.id.asc())
        ).all()
    )
    for lead in rows:
        if lead.id in diagnosed:
            continue
        if _one_step(ctx, lead):
            moved += 1
    return moved


def _diagnose(ctx: JobContext, diagnosed: set[str]) -> int:
    settings = get_settings()
    day = local_date(ctx.clock.now()).isoformat()
    key = f"diagnose_count:{day}"
    already = _counter(ctx.session, key)
    room = settings.diagnose_daily_limit - already
    if room <= 0:
        return 0
    leads = list(
        ctx.session.scalars(
            select(Lead)
            .where(Lead.status == "nuevo", Lead.source != "sistema")
            .order_by(Lead.opportunity_score.desc(), Lead.business.asc(), Lead.id.asc())
            .limit(room)
        ).all()
    )
    done = 0
    for lead in leads:
        if not _charge_llm(ctx, lead.id, "diagnoser"):
            break
        transition(ctx.session, lead, "diagnosticado", actor="agente", reason="diagnóstico")
        lead.diagnosis = {
            "markdown": f"Diagnóstico de {lead.business} en {lead.commune}.",
            "diagnosed_at": ctx.clock.now().isoformat(),
        }
        diagnosed.add(lead.id)
        done += 1
    if done:
        _put_counter(ctx.session, key, already + done, who="pipeline_tick")
    return done


def _charge_llm(ctx: JobContext, lead_id: str, agent: str) -> bool:
    repo = LlmCallRepository(ctx.session)
    budget = Decimal(str(get_settings().llm_daily_budget_usd))
    if repo.spend_today_usd(now=ctx.clock.now()) >= budget:
        EventRepository(ctx.session).append(
            agent=agent,
            level="warn",
            message="presupuesto LLM del día agotado",
            lead_id=lead_id,
            ts=ctx.clock.now(),
        )
        return False
    repo.add(
        LlmCall(
            agent=agent,
            model=get_settings().llm_model,
            prompt_name=agent,
            prompt_version="worker-1",
            tokens_in=120,
            tokens_out=40,
            cost_usd=Decimal("0.001"),
            latency_ms=1,
            ok=True,
            lead_id=lead_id,
            ts=ctx.clock.now(),
        )
    )
    return True


def _one_step(ctx: JobContext, lead: Lead) -> bool:
    status = lead.status
    if status == "diagnosticado":
        _ensure_artifact(ctx, lead, "landing_demo", f"output/demo/{lead.id}.html")
        transition(ctx.session, lead, "landing", actor="agente", reason="landing demo")
        return True
    if status == "landing":
        if _video_enabled(ctx.session):
            _ensure_artifact(ctx, lead, "storyboard", f"output/story/{lead.id}.md")
            transition(ctx.session, lead, "video", actor="agente", reason="storyboard")
            return True
        return _enter_pitch(ctx, lead)
    if status == "video":
        return _enter_pitch(ctx, lead)
    if status == "pitch_listo":
        return False
    if status == "respondio":
        return _maybe_book(ctx, lead)
    if status == "agendado":
        return _open_proposal(ctx, lead)
    if status == "propuesta":
        return _collect_payment(ctx, lead)
    if status == "pagado":
        return _start_production(ctx, lead)
    if status == "en_produccion":
        _touch_project(ctx, lead, "en_revision_cliente")
        transition(
            ctx.session,
            lead,
            "en_revision_cliente",
            actor="agente",
            reason="preview lista",
        )
        return True
    if status == "en_revision_cliente":
        _touch_project(ctx, lead, "aprobado", delivered=True)
        transition(ctx.session, lead, "entregado", actor="agente", reason="cliente aprueba")
        return True
    return False


def _ensure_artifact(ctx: JobContext, lead: Lead, kind: str, path: str) -> None:
    current = ArtifactRepository(ctx.session).list(lead_id=lead.id, limit=20)
    if any(item.kind == kind for item in current):
        return
    expires = None
    if kind == "landing_demo":
        expires = ctx.clock.now() + timedelta(days=get_settings().demo_ttl_days)
    ArtifactRepository(ctx.session).add(
        Artifact(
            lead_id=lead.id,
            kind=kind,
            version=1,
            path=path,
            expires_at=expires,
            meta={"lead_id": lead.id},
        )
    )


def _enter_pitch(ctx: JobContext, lead: Lead) -> bool:
    if needs_value_review(lead.estimated_value_clp) or lead.high_value:
        transition(ctx.session, lead, "revision", actor="agente", reason="deal alto valor")
        ensure_approval(
            ctx.session,
            lead_id=lead.id,
            kind="deal_alto_valor",
            payload={"estimated_value_clp": lead.estimated_value_clp},
        )
        return True
    _queue_messages(ctx, lead)
    transition(ctx.session, lead, "pitch_listo", actor="agente", reason="pitch revisado")
    return True


def _queue_messages(ctx: JobContext, lead: Lead) -> None:
    existing = MessageRepository(ctx.session).list(lead_id=lead.id, limit=20)
    if any(item.sequence_step == 1 and item.direction == "out" for item in existing):
        return
    scheduled = next_window_open(ctx.clock.now())
    subject, text, body_html = outreach_parts(
        business=lead.business,
        commune=lead.commune,
        step=1,
    )
    if lead.contact_email:
        queue_outbound(
            ctx,
            lead,
            channel="email_outreach",
            subject=subject,
            text=text,
            body_html=body_html,
            step=1,
            scheduled=scheduled,
        )
    if lead.instagram_handle:
        _add_manual(ctx, lead, "instagram", text, scheduled)
    if lead.linkedin_url:
        _add_manual(ctx, lead, "linkedin", text, scheduled)
    if lead.phone_public and not lead.contact_email:
        _add_manual(ctx, lead, "whatsapp", text, scheduled)
    lead.next_action_at = scheduled


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


def _add_manual(ctx: JobContext, lead: Lead, channel: str, text: str, scheduled: object) -> None:
    if channel not in MANUAL_CHANNELS:
        return
    MessageRepository(ctx.session).add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="out",
            channel=channel,
            sequence_step=1,
            status="manual_pending",
            subject=None,
            body_text=text[:400],
            check_result={"approved": False, "reasons": ["canal manual"]},
            scheduled_at=scheduled,
            created_at=ctx.clock.now(),
        )
    )


def _latest_intent(ctx: JobContext, lead: Lead) -> str | None:
    rows = MessageRepository(ctx.session).list(lead_id=lead.id, limit=50)
    inbound = [row for row in rows if row.direction == "in" and row.intent]
    if not inbound:
        return None
    return inbound[-1].intent


def _maybe_book(ctx: JobContext, lead: Lead) -> bool:
    intent = _latest_intent(ctx, lead)
    if intent not in {"interesado", "agendar"}:
        return False
    link = ctx.ports.bookings.link_for(lead.id)
    events = ctx.ports.bookings.poll()
    matched = [item for item in events if item.lead_id == lead.id]
    diagnosis = dict(lead.diagnosis or {})
    diagnosis["booking_link"] = link
    lead.diagnosis = diagnosis
    if not matched:
        return False
    transition(ctx.session, lead, "agendado", actor="agente", reason="agenda confirmada")
    return True


def _split_iva(total: int) -> tuple[int, int, int]:
    if get_settings().prices_include_iva:
        net = round(total / 1.19)
        return net, total - net, total
    iva = round(total * 0.19)
    return total, iva, total + iva


def _open_proposal(ctx: JobContext, lead: Lead) -> bool:
    orders = OrderRepository(ctx.session).list(lead_id=lead.id, limit=5)
    if not orders:
        total_price = offer_price_clp()
        net, iva, total = _split_iva(total_price)
        order = OrderRepository(ctx.session).add(
            Order(
                lead_id=lead.id,
                package_code=_PACKAGE["code"],
                amount_clp=net,
                iva_clp=iva,
                total_clp=total,
                deposit_percent=get_settings().deposit_percent,
                status="pending",
                created_at=ctx.clock.now(),
            )
        )
        deposit = total * get_settings().deposit_percent // 100
        pref = ctx.ports.payments.create_preference(
            order.id,
            f"Anticipo {lead.business}",
            deposit,
        )
        patch_fields(
            ctx.session,
            order,
            checkout_url=pref.url,
            provider_preference_id=pref.preference_id,
        )
        _ensure_artifact(ctx, lead, "propuesta", f"output/propuesta/{lead.id}.html")
    transition(ctx.session, lead, "propuesta", actor="agente", reason="propuesta emitida")
    return True


def _collect_payment(ctx: JobContext, lead: Lead) -> bool:
    orders = OrderRepository(ctx.session).list(lead_id=lead.id, limit=5)
    if not orders:
        return False
    order = orders[0]
    facts = [item for item in ctx.ports.payments.poll() if item.order_id == order.id]
    if not facts or facts[0].status not in {"approved", "paid"}:
        return False
    fact = facts[0]
    PaymentRepository(ctx.session).add(
        Payment(
            order_id=order.id,
            provider="mercadopago",
            provider_payment_id=fact.provider_payment_id,
            status=fact.status,
            amount_clp=fact.amount_clp,
            raw={"source": "simulacion"},
            received_at=ctx.clock.now(),
        )
    )
    patch_fields(ctx.session, order, status="deposit_paid")
    transition(ctx.session, lead, "pagado", actor="webhook", reason="pago aprobado")
    return True


def _project_for(ctx: JobContext, lead: Lead) -> Project | None:
    rows = ProjectRepository(ctx.session).list(lead_id=lead.id, limit=5)
    return rows[0] if rows else None


def _start_production(ctx: JobContext, lead: Lead) -> bool:
    orders = OrderRepository(ctx.session).list(lead_id=lead.id, limit=5)
    if not orders:
        return False
    if _project_for(ctx, lead) is None:
        ProjectRepository(ctx.session).add(
            Project(
                order_id=orders[0].id,
                lead_id=lead.id,
                status="en_produccion",
                revisions_used=0,
                max_revisions=_PACKAGE["revisions"],
                delivered_at=None,
            )
        )
    transition(ctx.session, lead, "en_produccion", actor="agente", reason="inicio de producción")
    return True


def _touch_project(
    ctx: JobContext,
    lead: Lead,
    project_status: str,
    *,
    delivered: bool = False,
) -> None:
    project = _project_for(ctx, lead)
    if project is None:
        return
    fields: dict[str, object] = {"status": project_status}
    if delivered:
        fields["delivered_at"] = ctx.clock.now()
    patch_fields(ctx.session, project, **fields)
