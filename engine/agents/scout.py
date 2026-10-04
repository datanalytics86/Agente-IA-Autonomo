"""Scout: busca leads y los deja en `nuevo`. No abre sockets en demo."""

from __future__ import annotations

from agents.base import Lead, load_leads
from agents.catalog import (
    COMMUNE_CITY,
    DEMO_HIGH_VALUE_CATEGORIES,
    THEME_BY_CATEGORY,
    TONE_BY_CATEGORY,
)
from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import iter_leads, log_event, prepare_db, start_of_local_day
from core.config import get_settings
from core.errors import DuplicateLeadError
from db.models import Lead as DbLead
from db.normalize import normalize_business
from db.repositories import LeadRepository, SettingsRepository
from db.session import session_scope
from integrations.pagespeed.base import WebAuditor, build_auditor
from integrations.places.base import DemoSource, LeadSource, PlaceHit, build_places


def _multi_site(name: str) -> bool:
    folded = normalize_business(name)
    return "multi sede" in folded or "multisede" in folded or "sucursales" in folded


def _package_value(category: str, has_website: bool, reviews: int) -> int:
    if not has_website and reviews >= 40 and category in DEMO_HIGH_VALUE_CATEGORIES:
        return 450_000
    if not has_website:
        return 350_000
    return 250_000


class ScoutAgent:
    def __init__(
        self,
        source: LeadSource | None = None,
        auditor: WebAuditor | None = None,
    ) -> None:
        self.source = source
        self.auditor = auditor

    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        settings = get_settings()
        source = self.source or build_places(settings)
        auditor = self.auditor or build_auditor(settings)
        communes = [item for item in settings.scout_commune_list if item]
        categories = [item for item in settings.scout_category_list if item in THEME_BY_CATEGORY]
        if not communes or not categories:
            return AgentResult(lead_id=None, ok=True, events=[], output={"ids": []})

        eligible = [item for item in categories if item in DEMO_HIGH_VALUE_CATEGORIES]
        force = bool(ctx.force_high_value and settings.app_mode == "demo" and eligible)
        remaining = _remaining_quota(ctx, settings.scout_daily_limit)
        wanted = min(max(ctx.count, 0), remaining)
        if wanted <= 0:
            message = "cuota diaria de scout alcanzada"
            log_event("Scout", message, level="warn", session=ctx.session)
            return AgentResult(lead_id=None, ok=True, events=[message], output={"ids": []})

        pairs = [(commune, category) for commune in communes for category in categories]
        slots = _slots(ctx, pairs, wanted, force, eligible[0] if force else "")
        known_places, known_names = _known(ctx)
        created: list[str] = []
        origin = "outbound_demo" if isinstance(source, DemoSource) else "outbound_places"
        forced_left = force
        for index, (commune, category) in enumerate(slots):
            use_force = forced_left and category in DEMO_HIGH_VALUE_CATEGORIES
            lead_id = _take_one(
                ctx,
                source,
                auditor,
                commune,
                category,
                origin,
                known_places,
                known_names,
                forced=use_force,
            )
            if lead_id is None:
                continue
            created.append(lead_id)
            if use_force:
                forced_left = False
            if index == 0 and force and not use_force:
                # El cupo forzado sigue disponible para el próximo rubro elegible.
                pass
        if created:
            names = ", ".join(sorted({_commune_of(ctx, item) for item in created}))
            message = f"{len(created)} leads nuevos en {names}"
            log_event(
                "Scout",
                message,
                session=ctx.session,
                meta={"ids": created, "count": len(created)},
            )
        else:
            message = "scout sin leads nuevos"
            log_event("Scout", message, session=ctx.session)
        return AgentResult(
            lead_id=created[0] if len(created) == 1 else None,
            ok=True,
            events=[message],
            output={"ids": created},
        )


def _remaining_quota(ctx: AgentContext, limit: int) -> int:
    start = start_of_local_day()
    created = 0
    for lead in iter_leads(ctx.session):
        if lead.created_at >= start and lead.source in {"outbound_demo", "outbound_places"}:
            created += 1
    return max(0, limit - created)


def _slots(
    ctx: AgentContext,
    pairs: list[tuple[str, str]],
    count: int,
    force: bool,
    eligible: str,
) -> list[tuple[str, str]]:
    repo = SettingsRepository(ctx.session)
    cursor = repo.get("scout_cursor", {"i": 0})
    start = int(cursor.get("i", 0)) if isinstance(cursor, dict) else 0
    chosen = [pairs[(start + offset) % len(pairs)] for offset in range(count)]
    repo.put("scout_cursor", {"i": start + count}, updated_by="scout")
    if not force:
        return chosen
    if any(category in DEMO_HIGH_VALUE_CATEGORIES for _, category in chosen):
        return chosen
    commune = chosen[0][0]
    chosen[0] = (commune, eligible)
    return chosen


def _known(ctx: AgentContext) -> tuple[set[str], set[tuple[str, str]]]:
    places: set[str] = set()
    names: set[tuple[str, str]] = set()
    for lead in iter_leads(ctx.session):
        if lead.place_id:
            places.add(lead.place_id)
        names.add((normalize_business(lead.business), lead.commune))
    return places, names


def _take_one(
    ctx: AgentContext,
    source: LeadSource,
    auditor: WebAuditor,
    commune: str,
    category: str,
    origin: str,
    known_places: set[str],
    known_names: set[tuple[str, str]],
    *,
    forced: bool,
) -> str | None:
    settings = get_settings()
    hits = source.search(commune, category, limit=5)
    for hit in hits:
        if not _acceptable(hit, settings.scout_min_rating, settings.scout_min_reviews):
            continue
        if hit.place_id in known_places:
            continue
        key = (normalize_business(hit.name), commune)
        if key in known_names:
            continue
        lead = _build_lead(hit, commune, category, origin, auditor, forced)
        try:
            LeadRepository(ctx.session).add(lead)
        except DuplicateLeadError:
            continue
        known_places.add(hit.place_id)
        known_names.add(key)
        return lead.id
    return None


def _acceptable(hit: PlaceHit, min_rating: float, min_reviews: int) -> bool:
    from integrations.places.base import accepts

    return accepts(hit, min_rating=min_rating, min_reviews=min_reviews)


def _build_lead(
    hit: PlaceHit,
    commune: str,
    category: str,
    origin: str,
    auditor: WebAuditor,
    forced: bool,
) -> DbLead:
    settings = get_settings()
    audit = auditor.audit(hit.website_uri)
    email = audit.contact_email if audit.contact_email and audit.contact_email_source_url else None
    multi = _multi_site(hit.name)
    high = bool(forced or multi)
    if high:
        value = settings.hitl_value_clp
        reason = (
            "Demo de alto valor en rubro sujeto a revisión humana."
            if forced and not multi
            else "Señal de multi-sede: queda para revisión humana."
        )
    else:
        value = _package_value(category, bool(hit.website_uri), int(hit.user_rating_count or 0))
        if hit.website_uri:
            reason = f"Sitio presente y oportunidad {audit.opportunity_score} en {commune}."
        else:
            reason = f"Sin sitio propio en {commune}."
    payload = audit.model_dump()
    payload["scout_reason"] = reason
    return DbLead(
        source=origin,
        business=hit.name,
        category=category,
        city=COMMUNE_CITY.get(commune, commune),
        commune=commune,
        address_public=hit.formatted_address or None,
        place_id=hit.place_id,
        google_maps_uri=hit.google_maps_uri,
        website_url=hit.website_uri,
        website_audit=payload,
        opportunity_score=audit.opportunity_score,
        rating=hit.rating,
        reviews=hit.user_rating_count,
        contact_email=email,
        contact_email_source_url=audit.contact_email_source_url if email else None,
        instagram_handle=audit.instagram_handle,
        phone_public=hit.national_phone_number,
        status="nuevo",
        estimated_value_clp=value,
        high_value=high,
        tone=TONE_BY_CATEGORY.get(category, "tu"),
    )


def _commune_of(ctx: AgentContext, lead_id: str) -> str:
    lead = LeadRepository(ctx.session).get(lead_id)
    return lead.commune if lead is not None else ""


def run_scout(count: int = 3, force_high_value: bool = True) -> list[Lead]:
    """Compatibilidad del CLI. Persiste en la base y devuelve la proyección."""
    prepare_db()
    with session_scope() as session:
        result = ScoutAgent().run(
            AgentContext(session, count=count, force_high_value=force_high_value)
        )
        created = set(result.output.get("ids") or [])
    if not created:
        return []
    return [lead for lead in load_leads() if lead.id in created]
