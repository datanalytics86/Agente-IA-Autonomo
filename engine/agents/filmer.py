"""Filmer — script/storyboard vertical 10–15s (o integración video si hay API)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from agents.base import (
    OUTPUT_DIR,
    Lead,
    LeadStatus,
    leads_by_status,
    log_event,
    read_prompt,
    upsert_lead,
)


def _storyboard(lead: Lead) -> str:
    _ = read_prompt("filmer")
    return f"""# Storyboard vertical 10–15s — {lead.business}
Formato: 9:16 · voz en off español chileno · subtítulos grandes

| Seg | Plano | Visual | Audio / texto en pantalla |
|-----|-------|--------|---------------------------|
| 0–3 | Apertura | Fachada / barrio {lead.commune} o mockup del rubro {lead.category} | “¿Buscas {lead.category} en {lead.commune}?” |
| 3–7 | Prueba social | Estrellas {lead.rating}★ y {lead.reviews} reseñas (gráfico simple) | “Vecinos ya confían en {lead.business}.” |
| 7–11 | Oferta | Mockup de la landing en celular | “Agenda fácil, sin dar vueltas.” |
| 11–15 | CTA | Logo + URL / IG | “Escríbenos o reserva en el link.” · música suave fade out |

## Notas de producción
- Sin hype ni emojis spam.
- No inventar teléfonos ni promociones falsas.
- Si no hay API de video, este storyboard es el entregable.
- Duración objetivo: 12s.

## Script voz en off (aprox. 12s)
“En {lead.commune}, {lead.business} te atiende con claridad.
Mira su nueva presencia online: servicios, reseñas y reserva en un solo lugar.
Entra al link y agenda en minutos.”
"""


def film_lead(lead: Lead) -> Lead:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    storyboard = _storyboard(lead)
    lead.storyboard = storyboard

    video_api = os.getenv("VIDEO_API_KEY") or os.getenv("RUNWAY_API_KEY")
    out_path = OUTPUT_DIR / f"storyboard_{lead.id[-6:]}.md"
    out_path.write_text(storyboard, encoding="utf-8")
    lead.video_path = str(out_path)

    if video_api:
        # Extensión prod: generar video real; en demo solo documentamos
        log_event(
            "Filmer",
            f"API video detectada pero modo demo usa storyboard · {lead.business}",
            level="info",
        )
    else:
        log_event(
            "Filmer",
            f"storyboard 12s · {lead.business} (sin API de video)",
            meta={"lead_id": lead.id, "path": str(out_path)},
        )

    if lead.status != LeadStatus.REVISION:
        lead.status = LeadStatus.VIDEO
    upsert_lead(lead)
    return lead


def run_filmer(leads: Optional[list[Lead]] = None) -> list[Lead]:
    targets = leads if leads is not None else leads_by_status(LeadStatus.LANDING)
    out: list[Lead] = []
    for lead in targets:
        if lead.status == LeadStatus.LANDING or (
            lead.status == LeadStatus.REVISION and lead.landing_path
        ):
            out.append(film_lead(lead))
    log_event("Filmer", f"{len(out)} piezas de video/storyboard")
    return out
