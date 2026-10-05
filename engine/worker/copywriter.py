"""Fallback de outreach si el Diagnoser no dejó pitch. El Checker lo tiene que poder aprobar."""

from __future__ import annotations

import html

from core.config import get_settings

MANUAL_CHANNELS = frozenset({"instagram", "linkedin", "whatsapp"})


def agency_label() -> str:
    name = get_settings().agency_name.strip()
    return name or "Agencia Demo"


def checker_settings() -> dict[str, object]:
    settings = get_settings()
    return {
        "agency_name": agency_label(),
        "price_min_clp": settings.price_min_clp,
        "price_max_clp": settings.price_max_clp,
        "public_base_url": settings.public_base_url,
        "agency_email": settings.agency_email,
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
) -> tuple[str, str, str]:
    """Asunto, texto y HTML mínimo. El cuerpo trae identidad, precio y baja."""
    settings = get_settings()
    agency = agency_label()
    price = _clp(offer_price_clp())
    base = settings.public_base_url.rstrip("/") or "http://localhost"
    follow = {
        1: "Si le interesa, puedo enviarle una propuesta.",
        2: "Le dejo el mismo dato, por si no alcanzó a verlo.",
        3: "Cierro el tema por ahora; queda a su disposición.",
    }.get(step, "Si le interesa, puedo enviarle una propuesta.")
    subject = f"Landing para {business}"
    text = (
        f"Hola. Te escribo de {agency}. "
        f"Vi {business} en {commune}. "
        f"La landing queda en {price} CLP. "
        f"{follow} "
        f"Si no quieres más correos responde BAJA: {base}/baja."
    )
    body_html = f"<p>{html.escape(text)}</p>"
    return subject, text, body_html
