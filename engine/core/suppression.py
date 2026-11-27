"""Una sola lectura de la lista de supresión. No abre sockets."""

from __future__ import annotations

import unicodedata

from sqlalchemy.orm import Session

from db.models import Lead, Suppression
from db.repositories import SuppressionRepository

_GENERIC_LOCAL = frozenset(
    {
        "abogados",
        "admin",
        "administracion",
        "atencion",
        "comercial",
        "consultas",
        "contabilidad",
        "contacto",
        "correo",
        "estudio",
        "gerencia",
        "hola",
        "info",
        "oficina",
        "recepcion",
        "secretaria",
        "ventas",
    }
)
_DETAIL_MAX = 2000


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_domain(value: str) -> str:
    """Dominio del correo: minúsculas, sin espacios y sin punto final."""
    text = value.strip().lower()
    if "@" in text:
        text = text.rsplit("@", 1)[1].strip()
    return text.rstrip(".")


def website_domain(value: str) -> str:
    """Host del sitio: sin esquema, ruta ni www, y con normalize_domain."""
    text = value.strip().lower()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/")[0].split("?")[0].split("#")[0].strip()
    if text.startswith("www."):
        text = text[4:]
    return normalize_domain(text)


def normalize_email(value: str) -> str:
    """Correo en minúsculas. El dominio queda sin punto final."""
    text = value.strip().lower()
    if "@" not in text:
        return text
    local, domain = text.rsplit("@", 1)
    return f"{local.strip()}@{normalize_domain(domain)}"


def generic_local_part(email: str) -> bool:
    """True si el buzón es de la oficina, no de una persona."""
    normalized = normalize_email(email)
    if "@" not in normalized:
        return False
    return _fold(normalized.split("@", 1)[0]) in _GENERIC_LOCAL


def is_suppressed(session: Session, lead: object) -> bool:
    """True si el lead, su correo o su estudio ya están en la lista."""
    repo = SuppressionRepository(session)
    email = normalize_email(str(getattr(lead, "contact_email", None) or ""))
    if email and repo.contains("email", email):
        return True
    domain = normalize_domain(email) if "@" in email else ""
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


def _detail(text: str | None) -> str | None:
    if not text:
        return None
    return text[:_DETAIL_MAX]


def _remember(row: Suppression, channel: str, detail: str | None) -> Suppression:
    row.source = channel
    if detail is not None:
        row.detail = detail
    return row


def record_opt_out(
    session: Session,
    lead: Lead,
    *,
    channel: str,
    reason: str,
    text: str | None = None,
) -> list[Suppression]:
    """Cierra el correo y el estudio. El dominio solo si es el del sitio."""
    repo = SuppressionRepository(session)
    detail = _detail(text)
    rows: list[Suppression] = []
    email = normalize_email(lead.contact_email or "")
    if email:
        rows.append(
            _remember(repo.add("email", email, reason=reason, source=channel), channel, detail)
        )
    place_id = (lead.place_id or "").strip() or lead.id
    if place_id:
        rows.append(
            _remember(repo.add("lead", place_id, reason=reason, source=channel), channel, detail)
        )
    mail_domain = normalize_domain(email) if "@" in email else ""
    site_domain = website_domain(lead.website_url or "")
    if mail_domain and site_domain and mail_domain == site_domain:
        rows.append(
            _remember(
                repo.add("domain", mail_domain, reason=reason, source=channel),
                channel,
                detail,
            )
        )
    return rows
