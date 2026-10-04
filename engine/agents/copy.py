"""Textos deterministas. Solo usan campos presentes en los datos del lead."""

from __future__ import annotations

from typing import Any

from agents.catalog import CATEGORY_LABELS, TONE_BY_CATEGORY
from agents.schemas import (
    CycleDecision,
    DailyDigest,
    DeliveryNote,
    DiagnosisOutput,
    FaqItem,
    FilmerOutput,
    JudgeVerdict,
    LandingCopy,
    MobileIntent,
    MobileReply,
    Opportunity,
    PersonalizationFact,
    PitchPlan,
    ProposalOutput,
    ScoutLeadDraft,
    ScoutOutput,
    ServiceItem,
    Shot,
)
from integrations.llm.base import register_fallback


def clp(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


def _tone(data: dict[str, Any]) -> str:
    category = str(data.get("category") or "")
    tone = data.get("tone")
    if tone in {"tu", "usted"}:
        return str(tone)
    return TONE_BY_CATEGORY.get(category, "tu")


def _facts(data: dict[str, Any]) -> list[PersonalizationFact]:
    facts: list[PersonalizationFact] = []
    business = data.get("business")
    commune = data.get("commune")
    if business:
        facts.append(PersonalizationFact(field="business", text=f"El negocio se llama {business}."))
    if commune:
        facts.append(PersonalizationFact(field="commune", text=f"Está en {commune}."))
    reviews = data.get("reviews")
    if isinstance(reviews, int) and reviews > 0:
        facts.append(
            PersonalizationFact(field="reviews", text=f"Tiene {reviews} reseñas públicas.")
        )
    rating = data.get("rating")
    if (
        isinstance(rating, (int, float))
        and not isinstance(rating, bool)
        and data.get("rating_known")
    ):
        facts.append(
            PersonalizationFact(field="rating", text=f"La valoración pública es {rating}.")
        )
    return facts


def _pitch(data: dict[str, Any]) -> tuple[str, str]:
    business = str(data.get("business") or "el negocio")
    commune = str(data.get("commune") or "su comuna")
    agency = str(data.get("agency_name") or "").strip()
    tone = _tone(data)
    has_website = bool(data.get("has_website"))
    price = data.get("price_clp")
    public = str(data.get("public_base_url") or "").rstrip("/")
    reviews = data.get("reviews") if isinstance(data.get("reviews"), int) else None
    rating = data.get("rating") if data.get("rating_known") else None

    if has_website:
        gap = f"El sitio público de {business} en {commune} se ve desactualizado."
    else:
        gap = f"No aparece un sitio propio de {business} en {commune}."
    reputation = ""
    if rating is not None and reviews:
        reputation = f" La ficha pública muestra {rating} de 5 y {reviews} reseñas."
    elif reviews:
        reputation = f" La ficha pública muestra {reviews} reseñas."

    if tone == "usted":
        offer = "Podemos armar una landing clara, con los datos públicos que ya existen."
        opt_out = "Si no es de interés, responda BAJA y no volveremos a escribir."
        hello = "Estimados:"
    else:
        offer = "Podemos armar una landing clara, con los datos públicos que ya existen."
        opt_out = "Si no es de interés, responde BAJA y no volvemos a escribir."
        hello = "Hola:"

    price_line = ""
    if isinstance(price, int) and 250_000 <= price <= 450_000:
        price_line = f" El paquete orientativo es ${clp(price)} CLP."
    link_line = ""
    if public:
        link_line = f"\nDetalle en {public}/agendar."
    sign = f"\n{agency}" if agency else ""
    subject = f"Sitio para {business} en {commune}"
    body = f"{hello}\n\n{gap}{reputation}\n\n{offer}{price_line}\n\n{opt_out}{link_line}{sign}\n"
    return subject, body


def diagnosis_fallback(data: dict[str, Any]) -> DiagnosisOutput:
    has_website = bool(data.get("has_website"))
    high_value = bool(data.get("high_value"))
    business = str(data.get("business") or "el negocio")
    commune = str(data.get("commune") or "la comuna")
    if high_value:
        package = "multi_sede"
        gap = (
            f"{business} en {commune} queda para revisión humana: "
            "el alcance sale de la banda publicada."
        )
    elif not has_website:
        package = "landing_pro"
        gap = f"{business} no muestra un sitio propio en {commune}."
    else:
        package = "landing_esencial"
        gap = f"El sitio de {business} en {commune} no está al día."
    subject, body = _pitch({**data, "price_clp": None if high_value else data.get("price_clp")})
    label = CATEGORY_LABELS.get(str(data.get("category") or ""), "el rubro")
    return DiagnosisOutput(
        gap_summary=gap,
        opportunities=[
            Opportunity(
                title="Presencia clara",
                detail=f"Una landing de {label} ayuda a quien busca el servicio en {commune}.",
            )
        ],
        recommended_package=package,
        tone=_tone(data),  # type: ignore[arg-type]
        personalization_facts=_facts(data),
        pitch_subject=subject,
        pitch_body=body,
    )


def landing_fallback(data: dict[str, Any]) -> LandingCopy:
    business = str(data.get("business") or "Negocio local")
    commune = str(data.get("commune") or "la comuna")
    label = CATEGORY_LABELS.get(str(data.get("category") or ""), "Servicios locales")
    return LandingCopy(
        hero_title=business,
        hero_subtitle=f"{label} en {commune}. Información clara y una forma simple de agendar.",
        services=[
            ServiceItem(
                title=label, detail=f"Atención en {commune}, con los datos que el negocio publique."
            ),
            ServiceItem(
                title="Primera visita", detail="La hora se confirma directo con el negocio."
            ),
            ServiceItem(title="Cómo llegar", detail="La dirección se muestra solo si es pública."),
        ],
        faqs=[
            FaqItem(
                question="¿Esta página es el sitio oficial?",
                answer="En modo demostración es una propuesta no oficial, no el sitio del negocio.",
            ),
            FaqItem(
                question="¿Cómo agendo?",
                answer=(
                    "Usa el enlace de agenda configurado. Si no está, el negocio confirma el canal."
                ),
            ),
        ],
        about=(
            f"{business} trabaja en {commune}. "
            "Esta página no inventa teléfonos, correos ni opiniones de clientes."
        ),
    )


def filmer_fallback(data: dict[str, Any]) -> FilmerOutput:
    business = str(data.get("business") or "el negocio")
    commune = str(data.get("commune") or "la comuna")
    return FilmerOutput(
        duration_s=12,
        shots=[
            Shot(start_s=0, end_s=3, visual=f"Fachada o barrio de {commune}", on_screen=business),
            Shot(
                start_s=3, end_s=7, visual="Servicios de la landing", on_screen="Servicios claros"
            ),
            Shot(start_s=7, end_s=12, visual="Llamado a agendar", on_screen="Agenda en el enlace"),
        ],
        voiceover=(
            f"En {commune}, {business} ordena su información en una sola página. "
            "Servicios, ubicación pública y una forma simple de agendar."
        ),
    )


def pitcher_fallback(data: dict[str, Any]) -> PitchPlan:
    channel = data.get("channel")
    if channel not in {"email_outreach", "instagram", "linkedin"}:
        channel = "instagram"
    manual = channel != "email_outreach"
    subject = str(data.get("pitch_subject") or "Sitio para tu negocio")
    body = str(data.get("pitch_body") or "")
    return PitchPlan(channel=channel, subject=subject, body_text=body, manual=manual)


def judge_fallback(data: dict[str, Any]) -> JudgeVerdict:
    approved = bool(data.get("layer1_approved"))
    if approved:
        reason = "fallback determinista sin XAI_API_KEY: la capa 2 acompaña a la capa 1"
        score = 100
    else:
        reason = (
            "fallback determinista sin XAI_API_KEY: la capa 2 no aprueba porque la capa 1 rechazó"
        )
        score = 0
    return JudgeVerdict(approved=approved, score=score, reasons=[reason], fallback=True)


def classifier_fallback(data: dict[str, Any]) -> MobileIntent:
    forced = data.get("deterministic_intent")
    if forced == "opt_out":
        return MobileIntent(intent="opt_out", confidence=1.0, reasons=["opt-out determinista"])
    return MobileIntent(
        intent="otro",
        confidence=0.4,
        reasons=["fallback determinista sin XAI_API_KEY: no hay auto-respuesta"],
    )


def mobile_fallback(data: dict[str, Any]) -> MobileReply:
    intent = classifier_fallback(data)
    return MobileReply(
        intent=intent.intent,
        confidence=intent.confidence,
        reply="",
        needs_human=intent.intent not in {"opt_out"} or intent.confidence < 0.8,
    )


def closer_fallback(data: dict[str, Any]) -> ProposalOutput:
    business = str(data.get("business") or "el negocio")
    price = int(data.get("price_clp") or 0)
    revisions = int(data.get("revisions") or 1)
    deposit = int(data.get("deposit_percent") or 50)
    include = bool(data.get("includes_iva", True))
    return ProposalOutput(
        title=f"Propuesta para {business}",
        scope=["Landing con los datos entregados por el cliente", "Publicación tras el saldo"],
        timeline="Entrega orientativa en 10 días hábiles tras el anticipo y el material.",
        revisions=revisions,
        price_clp=price,
        includes_iva=include,
        deposit_percent=deposit,
    )


def delivery_fallback(data: dict[str, Any]) -> DeliveryNote:
    path = str(data.get("portal_path") or "/proyecto")
    return DeliveryNote(
        portal_path=path,
        summary="Falta el material del cliente para producir la landing.",
        pending_items=["logo", "fotos propias", "dirección", "teléfono", "horarios", "servicios"],
    )


def reporter_fallback(data: dict[str, Any]) -> DailyDigest:
    counts = data.get("leads_by_status")
    if not isinstance(counts, dict):
        counts = {}
    clean = {str(key): int(value) for key, value in counts.items()}
    pending = int(data.get("pending_approvals") or 0)
    spend = float(data.get("llm_spend_usd") or 0)
    return DailyDigest(
        leads_by_status=clean,
        pending_approvals=pending,
        llm_spend_usd=spend,
        summary=f"{pending} aprobaciones pendientes. Gasto LLM del día: {spend:.4f} USD.",
    )


def scout_fallback(data: dict[str, Any]) -> ScoutOutput:
    raw = data.get("leads")
    drafts: list[ScoutLeadDraft] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                drafts.append(ScoutLeadDraft.model_validate(item))
    return ScoutOutput(leads=drafts)


def orchestrator_fallback(data: dict[str, Any]) -> CycleDecision:
    notes = data.get("notes")
    return CycleDecision(
        ran_scout=bool(data.get("ran_scout")),
        advanced=int(data.get("advanced") or 0),
        notes=[str(item) for item in notes] if isinstance(notes, list) else [],
    )


def register_agent_fallbacks() -> None:
    register_fallback("scout", scout_fallback)
    register_fallback("diagnoser", diagnosis_fallback)
    register_fallback("builder", landing_fallback)
    register_fallback("filmer", filmer_fallback)
    register_fallback("pitcher", pitcher_fallback)
    register_fallback("checker_judge", judge_fallback)
    register_fallback("mobile_classifier", classifier_fallback)
    register_fallback("mobile", mobile_fallback)
    register_fallback("closer", closer_fallback)
    register_fallback("delivery", delivery_fallback)
    register_fallback("reporter", reporter_fallback)
    register_fallback("orchestrator", orchestrator_fallback)
