"""Diagnoser — diagnóstico de oportunidad + pitch personalizado (ES-CL)."""

from __future__ import annotations

import os
from typing import Optional

from agents.base import (
    HIGH_VALUE_CLP,
    Lead,
    LeadStatus,
    leads_by_status,
    log_event,
    read_prompt,
    upsert_lead,
)


def _web_gap(lead: Lead) -> str:
    if not lead.has_website:
        return (
            "No aparece un sitio web propio claro en búsquedas públicas. "
            "Hoy compite solo con ficha de Maps/redes, lo que limita captura de leads 24/7."
        )
    year = lead.website_year or "antes de 2022"
    return (
        f"Tiene presencia web, pero el sitio luce desactualizado (aprox. {year}). "
        "Eso suele bajar confianza y conversión en móvil."
    )


def _price_band(lead: Lead) -> str:
    v = lead.estimated_value_clp
    if v >= HIGH_VALUE_CLP:
        return (
            f"Propuesta multi-unidad / paquete ampliado estimado en "
            f"${v:,} CLP (requiere validación humana).".replace(",", ".")
        )
    low, high = 250_000, 450_000
    return (
        f"Paquete landing profesional orientativo: ${low:,}–${high:,} CLP "
        f"(este lead ~${v:,} CLP). Pagos: transferencia, Mercado Pago o Webpay."
    ).replace(",", ".")


def template_diagnosis(lead: Lead) -> str:
    gap = _web_gap(lead)
    price = _price_band(lead)
    return (
        f"### Diagnóstico — {lead.business}\n"
        f"**Rubro:** {lead.category} · **Ubicación:** {lead.commune}, {lead.city}\n"
        f"**Reputación:** {lead.rating}★ ({lead.reviews} reseñas públicas)\n\n"
        f"**Brecha digital:** {gap}\n\n"
        f"**Oportunidad:** Una landing clara (servicios, prueba social, CTA de WhatsApp/agenda) "
        f"puede captar consultas de vecinos que hoy se van a la competencia con mejor presencia online.\n\n"
        f"**Oferta:** {price}\n"
        f"**Nota:** No se inventan teléfonos ni correos; el contacto se basa en canales públicos "
        f"o en respuesta del lead. Cumple enfoque Ley 21.719 (minimización de datos)."
    )


def template_pitch(lead: Lead) -> str:
    """Mensaje de prospección en español chileno profesional."""
    if lead.has_website:
        gancho = (
            f"Vi que {lead.business} en {lead.commune} tiene buena reputación "
            f"({lead.rating}★), pero el sitio se ve un poco desactualizado."
        )
    else:
        gancho = (
            f"Estuve revisando negocios de {lead.category} en {lead.commune} y "
            f"{lead.business} destaca por reseñas, pero no encontré una web propia clara."
        )

    formal = lead.category in {"legal", "salud", "servicios profesionales", "inmobiliaria"}
    saludo = "Estimado/a equipo" if formal else "Hola"
    usted = "puedan" if formal else "puedas"
    su = "su" if formal else "tu"

    price = lead.estimated_value_clp
    if price >= HIGH_VALUE_CLP:
        oferta = (
            "Para una red o multi-sede armamos un paquete a medida "
            "(landing + piezas cortas + seguimiento). Lo conversamos en una llamada breve."
        )
    else:
        oferta = (
            f"Trabajo con un paquete de landing responsive (5 secciones) orientado a pymes locales, "
            f"en el rango ${250_000:,}–${450_000:,} CLP, con pago por transferencia, "
            f"Mercado Pago o Webpay.".replace(",", ".")
        )

    return (
        f"{saludo},\n\n"
        f"{gancho} Eso suele dejar consultas en la mesa, sobre todo en celular.\n\n"
        f"Puedo armarles una landing simple y profesional (servicios, reseñas, cómo llegar y un CTA claro) "
        f"pensada para {lead.commune}, más un video vertical corto o storyboard para redes.\n\n"
        f"{oferta}\n\n"
        f"Si les hace sentido, me avisan y coordinamos 15 minutos sin compromiso. "
        f"Si no es de interés, respondan STOP y no vuelvo a escribir.\n\n"
        f"Saludos cordiales,\n"
        f"— Agente IA Autónomo (prospección automatizada asistida)\n"
        f"Canales: Instagram DM / email / LinkedIn · WhatsApp solo si ya hay conversación."
    )


def _try_llm_improve(lead: Lead, diagnosis: str, pitch: str) -> tuple[str, str]:
    """Si hay API key, podría mejorar textos. En demo sin key, retorna templates."""
    key = os.getenv("GROK_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return diagnosis, pitch
    # Extensión prod: llamar LLM con read_prompt("diagnoser") + contexto lead.
    # Por ahora no bloqueamos demo si la API falla; usamos templates de calidad.
    try:
        # Placeholder extensible — no falla el pipeline
        _ = read_prompt("diagnoser")
        return diagnosis, pitch
    except Exception:
        return diagnosis, pitch


def diagnose_lead(lead: Lead) -> Lead:
    diagnosis = template_diagnosis(lead)
    pitch = template_pitch(lead)
    diagnosis, pitch = _try_llm_improve(lead, diagnosis, pitch)

    lead.diagnosis = diagnosis
    lead.pitch = pitch

    if lead.estimated_value_clp >= HIGH_VALUE_CLP:
        lead.high_value = True
        lead.status = LeadStatus.REVISION
        lead.reason = (
            (lead.reason or "")
            + f" | Orchestrator: deal {lead.estimated_value_clp:,} CLP → revision manual".replace(",", ".")
        )
        log_event(
            "Orchestrator",
            f"deal {lead.estimated_value_clp:,} CLP → revision manual".replace(",", "."),
            level="warn",
            meta={"lead_id": lead.id, "business": lead.business},
        )
    else:
        lead.status = LeadStatus.DIAGNOSTICADO

    upsert_lead(lead)
    log_event(
        "Diagnoser",
        f"diagnóstico listo · {lead.business} → {lead.status.value}",
        meta={"lead_id": lead.id},
    )
    return lead


def run_diagnoser(leads: Optional[list[Lead]] = None) -> list[Lead]:
    targets = leads if leads is not None else leads_by_status(LeadStatus.NUEVO)
    # No re-diagnosticar los que ya están en revision por high-value sin pasar
    out: list[Lead] = []
    for lead in targets:
        if lead.status not in (LeadStatus.NUEVO,):
            continue
        out.append(diagnose_lead(lead))
    if not out and targets:
        # Si se pasan leads explícitos (p.ej. recién scouteados) con status nuevo
        for lead in targets:
            if lead.status == LeadStatus.NUEVO:
                out.append(diagnose_lead(lead))
    log_event("Diagnoser", f"{len(out)} leads diagnosticados")
    return out
