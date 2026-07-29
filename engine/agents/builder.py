"""Builder — genera landing HTML responsive (5 secciones)."""

from __future__ import annotations

import re
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


def _slug(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[áàä]", "a", s)
    s = re.sub(r"[éèë]", "e", s)
    s = re.sub(r"[íìï]", "i", s)
    s = re.sub(r"[óòö]", "o", s)
    s = re.sub(r"[úùü]", "u", s)
    s = s.replace("ñ", "n")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48] or "landing"


def _category_copy(category: str) -> dict[str, str]:
    defaults = {
        "hero_sub": "Atención cercana en tu comuna, con reserva simple y respuesta rápida.",
        "services": [
            "Diagnóstico o evaluación inicial",
            "Servicio principal del rubro",
            "Seguimiento y soporte post-atención",
        ],
        "cta": "Agenda tu hora",
    }
    packs = {
        "salud": {
            "hero_sub": "Cuidado profesional cerca de ti. Reserva online en minutos.",
            "services": ["Evaluación inicial", "Tratamientos", "Controles y seguimiento"],
            "cta": "Reserva tu hora",
        },
        "belleza": {
            "hero_sub": "Look renovado, con hora online y atención personalizada.",
            "services": ["Corte y color", "Tratamientos", "Paquetes del mes"],
            "cta": "Reserva tu hora",
        },
        "gastronomía": {
            "hero_sub": "Sabores de barrio. Carta clara y cómo llegar en un click.",
            "services": ["Carta del día", "Reservas", "Delivery / retiro"],
            "cta": "Ver carta y reservar",
        },
        "fitness": {
            "hero_sub": "Entrena con plan claro y cupos limitados en tu comuna.",
            "services": ["Clases grupales", "Plan personalizado", "Prueba sin compromiso"],
            "cta": "Agenda tu clase de prueba",
        },
        "legal": {
            "hero_sub": "Asesoría clara y confidencial. Primera consulta orientativa.",
            "services": ["Consulta inicial", "Representación", "Seguimiento de caso"],
            "cta": "Solicitar orientación",
        },
    }
    return packs.get(category, defaults)  # type: ignore[return-value]


def render_landing_html(lead: Lead) -> str:
    _ = read_prompt("builder")
    copy = _category_copy(lead.category)
    services = copy.get("services") or [
        "Servicio principal",
        "Atención personalizada",
        "Seguimiento",
    ]
    if isinstance(services, str):
        services = [services]
    hero_sub = copy.get("hero_sub", "Presencia digital profesional para tu negocio local.")
    cta = copy.get("cta", "Contáctanos")

    stars = "★" * int(min(5, max(1, round(lead.rating)))) + "☆" * (
        5 - int(min(5, max(1, round(lead.rating))))
    )
    services_html = "\n".join(
        f'        <article class="card"><h3>{s}</h3><p>Detalle orientativo para {lead.commune}.</p></article>'
        for s in services
    )

    return f"""<!DOCTYPE html>
<html lang="es-CL">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{lead.business} · {lead.commune}</title>
  <meta name="description" content="{lead.business} en {lead.commune}. {hero_sub}" />
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --text: #f2f5f8;
      --muted: #9aa8b5;
      --accent: #2dd4bf;
      --accent2: #38bdf8;
      --border: #2a3544;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
    }}
    a {{ color: var(--accent); }}
    header.hero {{
      padding: 3.5rem 1.25rem 2.5rem;
      background: linear-gradient(145deg, #132033 0%, #0f1419 60%, #0c2a28 100%);
      border-bottom: 1px solid var(--border);
    }}
    .wrap {{ max-width: 920px; margin: 0 auto; }}
    .badge {{
      display: inline-block;
      font-size: 0.75rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--accent);
      border: 1px solid var(--accent);
      border-radius: 999px;
      padding: 0.25rem 0.7rem;
      margin-bottom: 1rem;
    }}
    h1 {{ font-size: clamp(1.75rem, 4vw, 2.4rem); margin-bottom: 0.6rem; }}
    .sub {{ color: var(--muted); max-width: 36rem; margin-bottom: 1.4rem; }}
    .btn {{
      display: inline-block;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      color: #06201c;
      font-weight: 700;
      text-decoration: none;
      padding: 0.75rem 1.25rem;
      border-radius: 0.6rem;
    }}
    section {{ padding: 2.5rem 1.25rem; border-bottom: 1px solid var(--border); }}
    h2 {{ font-size: 1.35rem; margin-bottom: 1rem; }}
    .grid {{
      display: grid;
      gap: 1rem;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 0.85rem;
      padding: 1.1rem;
    }}
    .card h3 {{ font-size: 1.05rem; margin-bottom: 0.35rem; }}
    .card p {{ color: var(--muted); font-size: 0.95rem; }}
    .stars {{ color: #fbbf24; letter-spacing: 0.08em; }}
    footer {{
      padding: 2rem 1.25rem 3rem;
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .muted {{ color: var(--muted); }}
    ul.clean {{ list-style: none; }}
    ul.clean li {{ padding: 0.35rem 0; }}
    ul.clean li::before {{ content: "✓ "; color: var(--accent); }}
  </style>
</head>
<body>
  <!-- 1. Hero -->
  <header class="hero">
    <div class="wrap">
      <span class="badge">{lead.commune} · {lead.city}</span>
      <h1>{lead.business}</h1>
      <p class="sub">{hero_sub}</p>
      <a class="btn" href="#contacto">{cta}</a>
    </div>
  </header>

  <!-- 2. Servicios -->
  <section id="servicios">
    <div class="wrap">
      <h2>Servicios</h2>
      <div class="grid">
{services_html}
      </div>
    </div>
  </section>

  <!-- 3. Prueba social -->
  <section id="opiniones">
    <div class="wrap">
      <h2>Lo que dicen los vecinos</h2>
      <div class="card">
        <p class="stars">{stars}</p>
        <p><strong>{lead.rating} / 5</strong> · basándonos en {lead.reviews} reseñas públicas de referencia.</p>
        <p class="muted" style="margin-top:0.6rem">
          “Buen servicio y atención cercana. Ideal para gente del barrio.” — Cliente local (ejemplo de tono)
        </p>
      </div>
    </div>
  </section>

  <!-- 4. Ubicación / cómo llegar -->
  <section id="ubicacion">
    <div class="wrap">
      <h2>Dónde estamos</h2>
      <div class="card">
        <p><strong>{lead.commune}</strong>, {lead.city}, Chile</p>
        <p class="muted" style="margin-top:0.5rem">
          Indicaciones y mapa se completan con la dirección real del negocio (no inventamos datos privados).
        </p>
        <ul class="clean" style="margin-top:0.8rem">
          <li>Atención presencial en la comuna</li>
          <li>Reserva online o por mensaje</li>
          <li>Respuesta en horario hábil</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- 5. CTA / contacto -->
  <section id="contacto">
    <div class="wrap">
      <h2>¿Conversamos?</h2>
      <div class="card">
        <p>Déjanos tu nombre y el mejor canal para responderte. Sin spam.</p>
        <p style="margin-top:1rem">
          <a class="btn" href="https://calendly.com/demo-agente-ia/diagnostico" rel="noopener">
            Agendar llamada de 15 min
          </a>
        </p>
        <p class="muted" style="margin-top:1rem;font-size:0.9rem">
          Pagos referenciales del servicio digital: transferencia, Mercado Pago o Webpay.
          Si no deseas más mensajes de prospección, responde STOP.
        </p>
      </div>
    </div>
  </section>

  <footer>
    <div class="wrap">
      <p>{lead.business} · Landing demo generada por Agente IA Autónomo</p>
      <p>Lead ID: {lead.id} · Cumplimiento orientado a Ley 21.719 (datos personales)</p>
    </div>
  </footer>
</body>
</html>
"""


def build_landing(lead: Lead) -> Lead:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_slug(lead.business)}_{lead.id[-6:]}.html"
    path = OUTPUT_DIR / filename
    html = render_landing_html(lead)
    path.write_text(html, encoding="utf-8")

    lead.landing_path = str(path)
    if lead.status != LeadStatus.REVISION:
        lead.status = LeadStatus.LANDING
    upsert_lead(lead)
    log_event(
        "Builder",
        f"landing HTML · {lead.business} → {path.name}",
        meta={"lead_id": lead.id, "path": str(path)},
    )
    return lead


def run_builder(leads: Optional[list[Lead]] = None) -> list[Lead]:
    targets = leads if leads is not None else leads_by_status(LeadStatus.DIAGNOSTICADO)
    out: list[Lead] = []
    for lead in targets:
        if lead.status not in (LeadStatus.DIAGNOSTICADO,):
            # High-value en revision: igual generamos artefactos demo si se pide en pipeline
            if lead.status == LeadStatus.REVISION and lead.diagnosis:
                out.append(build_landing(lead))
            continue
        out.append(build_landing(lead))
    log_event("Builder", f"{len(out)} landings generadas")
    return out
