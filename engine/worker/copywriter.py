"""Borrador determinista de outreach. El Checker lo tiene que poder aprobar."""

from __future__ import annotations

import html

from core.compliance import legal_footer
from core.config import get_settings

MANUAL_CHANNELS = frozenset({"instagram", "linkedin", "whatsapp"})


def agency_label() -> str:
    return get_settings().agency_name.strip()


def checker_settings() -> dict[str, object]:
    settings = get_settings()
    return {
        "agency_name": agency_label(),
        "price_min_clp": settings.price_min_clp,
        "price_max_clp": settings.price_max_clp,
        "public_base_url": settings.public_base_url,
        "agency_email": settings.agency_email,
        "agency_legal_name": settings.agency_legal_name,
        "agency_rut": settings.agency_rut,
        "agency_address": settings.agency_address,
    }


def offer_price_clp() -> int:
    settings = get_settings()
    candidate = 350_000
    if settings.price_min_clp <= candidate <= settings.price_max_clp:
        return candidate
    return settings.price_min_clp


def _clp(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


def outreach_parts(
    *,
    business: str,
    commune: str,
    step: int,
    source: str | None = None,
) -> tuple[str, str, str]:
    """Asunto, texto y HTML mínimo. El cuerpo trae identidad, precio y baja."""
    settings = get_settings()
    agency = agency_label()
    price = _clp(offer_price_clp())
    follow = {
        1: "Si le interesa, puedo enviarle una propuesta.",
        2: "Le dejo el mismo dato, por si no alcanzó a verlo.",
        3: "Cierro el tema por ahora; queda a su disposición.",
    }.get(step, "Si le interesa, puedo enviarle una propuesta.")
    subject = f"Propuesta comercial: landing para {business}"
    text = (
        f"Hola. Te escribo de {agency}. "
        f"Vi {business} en {commune}. "
        f"La landing queda en {price} CLP. "
        f"{follow}\n\n"
        f"{legal_footer(settings, source)}"
    )
    body_html = "<p>" + "<br>".join(html.escape(line) for line in text.split("\n")) + "</p>"
    return subject, text, body_html
