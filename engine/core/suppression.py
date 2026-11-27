"""Una sola lectura de la lista de supresión. No abre sockets."""

from __future__ import annotations

import unicodedata

from sqlalchemy.orm import Session

from db.models import Lead, Suppression
from db.repositories import SuppressionRepository

_GENERIC_LOCAL = frozenset(
    {
        "admin",
        "comercial",
        "contact",
        "contacto",
        "hello",
        "hola",
        "info",
        "office",
        "oficina",
        "recepcion",
        "sales",
        "secretaria",
        "soporte",
        "support",
        "ventas",
    }
)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def generic_local_part(email: str) -> bool:
    """True si el buzón es de la oficina, no de una persona."""
    if "@" not in email:
        return False
    return _fold(email.split("@", 1)[0]) in _GENERIC_LOCAL


def is_suppressed(session: Session, lead: object) -> bool:
    """True si el lead, su correo o su estudio ya están en la lista."""
    repo = SuppressionRepository(session)
    email = str(getattr(lead, "contact_email", None) or "").strip()
    if email and repo.contains("email", email):
        return True
    if "@" in email:
        domain = email.split("@", 1)[1].strip()
        if domain and repo.contains("domain", domain):
            return True
    website = getattr(lead, "website_url", None)
    if website and repo.contains("domain", str(website)):
        return True
    instagram = getattr(lead, "instagram_handle", None)
    if instagram and repo.contains("instagram", str(instagram)):
        return True
    linkedin = getattr(lead, "linkedin_url", None)
    if linkedin and repo.contains("linkedin", str(linkedin)):
        return True
    phone = getattr(lead, "phone_public", None)
    if phone and repo.contains("phone", str(phone)):
        return True
    for raw in (getattr(lead, "place_id", None), getattr(lead, "id", None)):
        key = str(raw or "").strip()
        if key and repo.contains("lead", key):
            return True
    return False


def record_opt_out(
    session: Session,
    lead: Lead,
    *,
    channel: str,
    reason: str,
) -> list[Suppression]:
    """Guarda el correo. Un buzón genérico también cierra el estudio.

    Una baja no crea kind=domain: persona@gmail.com no puede apagar Gmail.
    """
    repo = SuppressionRepository(session)
    rows: list[Suppression] = []
    email = (lead.contact_email or "").strip()
    if email:
        rows.append(repo.add("email", email, reason=reason, source=channel))
    if email and generic_local_part(email):
        place_id = (lead.place_id or "").strip() or lead.id
        if place_id:
            rows.append(repo.add("lead", place_id, reason=reason, source=channel))
    return rows
