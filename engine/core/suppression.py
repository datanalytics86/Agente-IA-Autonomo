"""Una sola lectura de la lista de supresión. No abre sockets."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.compliance import _EMAIL_RE, _PHONE_RE
from db.models import Lead, Suppression
from db.normalize import contact_hash
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
_DETAIL_MAX = 500
_QUOTE_LINE = re.compile(r"(?i)(?:^el\b.+\bescribi[oó]\s*:|^on\b.+\bwrote\s*:)")
_SIMPLE_CLOSE = re.compile(
    r"(?i)^(?:saludos(?:\s+cordiales)?|atentamente|cordialmente|"
    r"un saludo|muchas gracias|gracias)[.!]?$"
)
_RUT_RE = re.compile(r"\b\d{1,2}(?:[.\s]?\d{3}){2}\s*-\s*[\dkK]\b")


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_SECOND_LEVEL = frozenset({"com", "co", "net", "org", "gob", "edu", "gov"})


def _hostname(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if "@" in text and "://" not in text and not text.startswith("//"):
        text = text.rsplit("@", 1)[1].strip()
    if "://" not in text and not text.startswith("//"):
        text = "//" + text
    host = (urlsplit(text).hostname or "").strip().lower().rstrip(".")
    if not host:
        return ""
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return ""


def normalize_domain(value: str) -> str:
    """Host del correo, con puerto y userinfo fuera, en punycode."""
    return _hostname(value)


def registrable_domain(host: str) -> str:
    """Últimos 2 labels, o 3 si el TLD es de dos niveles (com.ar, co.uk)."""
    labels = [part for part in host.split(".") if part]
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return ".".join(labels)


def website_domain(value: str) -> str:
    """Dominio registrable del sitio, sin www, puerto ni userinfo."""
    host = _hostname(value)
    if host.startswith("www."):
        host = host[4:]
    return registrable_domain(host)


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
    domain = registrable_domain(normalize_domain(email)) if "@" in email else ""
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


def clean_opt_out_text(text: str | None) -> str | None:
    """Extracto de la baja: sin cita, sin firma y sin teléfono ni RUT."""
    if not text:
        return None
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">") or _QUOTE_LINE.search(stripped):
            break
        if line.startswith("-- ") or stripped == "--":
            break
        if _SIMPLE_CLOSE.match(stripped):
            break
        kept.append(line)
    body = "\n".join(kept)
    body = _EMAIL_RE.sub("[correo]", body)
    body = _PHONE_RE.sub("[teléfono]", body)
    body = _RUT_RE.sub("[rut]", body)
    body = body.strip()
    if not body:
        return None
    return body[:_DETAIL_MAX]


def _remember(
    row: Suppression,
    channel: str,
    detail: str | None,
    *,
    keep_text: bool,
) -> Suppression:
    row.source = channel
    if keep_text and detail is not None:
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
    detail = clean_opt_out_text(text)
    rows: list[Suppression] = []
    email = normalize_email(lead.contact_email or "")
    if email:
        rows.append(
            _remember(
                repo.add("email", email, reason=reason, source=channel),
                channel,
                detail,
                keep_text=True,
            )
        )
    place_id = (lead.place_id or "").strip() or lead.id
    if place_id:
        rows.append(
            _remember(
                repo.add("lead", place_id, reason=reason, source=channel),
                channel,
                None,
                keep_text=False,
            )
        )
    mail_domain = registrable_domain(normalize_domain(email)) if "@" in email else ""
    site_domain = website_domain(lead.website_url or "")
    if mail_domain and site_domain and mail_domain == site_domain:
        rows.append(
            _remember(
                repo.add("domain", mail_domain, reason=reason, source=channel),
                channel,
                None,
                keep_text=False,
            )
        )
    return rows


def erase_personal_data(session: Session, lead: Lead) -> None:
    """Borra el extracto y los datos personales. La supresión, por hash, queda."""
    email = normalize_email(lead.contact_email or "")
    if email:
        digest = contact_hash("email", email)
        row = session.scalar(
            select(Suppression).where(
                Suppression.kind == "email",
                Suppression.value_hash == digest,
            )
        )
        if row is not None:
            row.detail = None
    lead.contact_email = None
    lead.contact_email_source_url = None
    lead.instagram_handle = None
    lead.linkedin_url = None
    lead.phone_public = None
    lead.address_public = None
    lead.consent = None
    lead.diagnosis = None
    lead.website_audit = None
    lead.anonymized_at = datetime.now(UTC)
    session.flush()
