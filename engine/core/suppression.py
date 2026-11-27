"""Una sola lectura de la lista de supresión. No abre sockets."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.compliance import _EMAIL_RE, _PHONE_RE
from db.models import Approval, Artifact, Event, Lead, Message, Suppression
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
_GMAIL_OPEN = re.compile(r"(?i)^el\b")
_GMAIL_WROTE = re.compile(r"(?i)\bescribi[oó]\s*:")
_OUTLOOK_RULE = re.compile(r"^_{4,}$")
_OUTLOOK_HEADER = re.compile(r"(?i)^(de|enviado|para|asunto)\s*:")
_OUTLOOK_NEXT = re.compile(r"(?i)^(enviado|para|asunto)\s*:")
_GREETING = re.compile(r"(?i)^(?:hola|estimad[oa]s?)\s*[,:]?\s*$")
_ORIGINAL = re.compile(r"(?i)^-{3,}\s*(?:mensaje original|original message)\s*-{3,}$")
_PHONE_SIG = re.compile(r"(?i)^(?:enviado desde mi|sent from my)\b")
_SIMPLE_CLOSE = re.compile(
    r"(?i)^(?:saludos(?:\s+cordiales)?|atentamente|cordialmente|"
    r"un saludo|muchas gracias|gracias)[.!]?$"
)
_RUT_RE = re.compile(r"\b\d{1,2}(?:[.\s]?\d{3}){2}\s*-\s*[\dkK]\b")


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_MAIL_TLDS = ("com", "cl", "es", "com.ar", "co.uk", "com.mx")
SHARED_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "yahoo.com",
        "yahoo.es",
        "ymail.com",
        "rocketmail.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "pm.me",
        "tutanota.com",
        "tuta.io",
        "zoho.com",
        "gmx.com",
        "gmx.net",
        "mail.com",
        "yandex.com",
        "fastmail.com",
        "vtr.net",
        "terra.cl",
        "entelchile.net",
        "movistar.cl",
        "tie.cl",
        "manquehue.net",
        "ctcinternet.cl",
        "123.cl",
        "surnet.cl",
        "telsur.cl",
        "wixsite.com",
        "blogspot.com",
        "github.io",
        "wordpress.com",
        "netlify.app",
        "vercel.app",
        "sites.google.com",
        "uchile.cl",
        "uc.cl",
        "udp.cl",
        "usach.cl",
        "udec.cl",
        "uai.cl",
        "unab.cl",
        "udd.cl",
        *(f"{name}.{tld}" for name in ("hotmail", "outlook", "live", "msn") for tld in _MAIL_TLDS),
    }
)


def normalize_host(value: str) -> str:
    """Host en minúsculas, IDNA, sin punto final y sin www. Nunca levanta."""
    try:
        text = (value or "").strip()
        if not text:
            return ""
        if "@" in text and "://" not in text and not text.startswith("//"):
            text = text.rsplit("@", 1)[1].strip()
        if "://" not in text and not text.startswith("//"):
            text = "//" + text
        host = (urlsplit(text).hostname or "").strip().lower().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        if not host:
            return ""
        return host.encode("idna").decode("ascii")
    except Exception:
        return ""


def _suffixes(host: str) -> list[str]:
    labels = [part for part in host.split(".") if part]
    return [".".join(labels[index:]) for index in range(max(len(labels) - 1, 0))]


def is_shared_host(value: str) -> bool:
    """True si el host, o un sufijo con borde de label, es un dominio compartido."""
    host = normalize_host(value)
    if not host:
        return False
    labels = [part for part in host.split(".") if part]
    for index, suffix in enumerate(_suffixes(host)):
        if suffix in SHARED_DOMAINS or labels[index] == "blogspot":
            return True
    return False


def host_is_suppressed(session: Session, value: str) -> bool:
    """True si ese host o un dominio padre, con borde de label, está cerrado."""
    host = normalize_host(value)
    if not host:
        return False
    repo = SuppressionRepository(session)
    return any(repo.contains("domain", suffix) for suffix in _suffixes(host))


def normalize_email(value: str) -> str:
    """Correo en minúsculas. El dominio queda sin punto final ni www."""
    text = value.strip().lower()
    if "@" not in text:
        return text
    local, domain = text.rsplit("@", 1)
    host = normalize_host(domain)
    if not host:
        return f"{local.strip()}@{domain.strip().rstrip('.')}"
    return f"{local.strip()}@{host}"


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
    if "@" in email and host_is_suppressed(session, email.split("@", 1)[1]):
        return True
    website = getattr(lead, "website_url", None)
    if website and host_is_suppressed(session, str(website)):
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


def _outlook_header(lines: list[str], index: int, stripped: str) -> bool:
    if _OUTLOOK_RULE.match(stripped):
        return True
    if not _OUTLOOK_HEADER.match(stripped):
        return False
    if "@" in stripped or "<" in stripped:
        return True
    if not stripped.lower().startswith("de"):
        return False
    for nxt in lines[index + 1 : index + 6]:
        text = nxt.strip()
        if not text:
            continue
        return _OUTLOOK_NEXT.match(text) is not None
    return False


def _cuts_quote(lines: list[str], index: int, stripped: str) -> bool:
    if stripped.startswith(">") or _QUOTE_LINE.search(stripped):
        return True
    if _outlook_header(lines, index, stripped):
        return True
    if _ORIGINAL.match(stripped) or _PHONE_SIG.search(stripped):
        return True
    nxt = lines[index + 1].strip() if index + 1 < len(lines) else ""
    return bool(_GMAIL_OPEN.match(stripped) and _GMAIL_WROTE.search(nxt))


def clean_opt_out_text(text: str | None) -> str | None:
    """Primer párrafo de la baja, sin cita, firma, teléfono ni RUT."""
    if not text:
        return None
    lines = text.splitlines()
    kept: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if kept:
                break
            continue
        if line.startswith("-- ") or stripped == "--":
            break
        if _cuts_quote(lines, index, stripped):
            break
        if _SIMPLE_CLOSE.match(stripped) and kept:
            break
        if _GREETING.match(stripped) and not kept:
            continue
        kept.append(line)
        if len(kept) >= 5:
            break
    body = "\n".join(kept)
    body = _EMAIL_RE.sub("[correo]", body)
    body = _PHONE_RE.sub("[teléfono]", body)
    body = _RUT_RE.sub("[rut]", body)
    body = body.strip()
    if not body:
        return None
    return body[:_DETAIL_MAX]


def _store(
    repo: SuppressionRepository,
    kind: str,
    value: str,
    *,
    channel: str,
    reason: str,
    detail: str | None,
    keep_text: bool,
) -> Suppression:
    """La primera baja fija source, extracto y fecha. La siguiente solo cuenta."""
    existed = repo.contains(kind, value)
    row = repo.add(kind, value, reason=reason, source=channel)
    if existed:
        row.count = int(row.count or 1) + 1
        row.last_at = datetime.now(UTC)
        return row
    row.count = 1
    row.last_at = row.created_at
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
    verbatim: bool = False,
) -> list[Suppression]:
    """Cierra el correo y el estudio. Un dominio compartido no se cierra."""
    repo = SuppressionRepository(session)
    if verbatim:
        detail = (text or "")[:_DETAIL_MAX] or None
    else:
        detail = clean_opt_out_text(text)
    rows: list[Suppression] = []
    email = normalize_email(lead.contact_email or "")
    if email:
        rows.append(
            _store(
                repo,
                "email",
                email,
                channel=channel,
                reason=reason,
                detail=detail,
                keep_text=True,
            )
        )
    place_id = (lead.place_id or "").strip() or lead.id
    if place_id:
        rows.append(
            _store(
                repo,
                "lead",
                place_id,
                channel=channel,
                reason=reason,
                detail=None,
                keep_text=False,
            )
        )
    host = normalize_host(email.split("@", 1)[1]) if "@" in email else ""
    if host and is_shared_host(host):
        place = (lead.place_id or "").strip()
        seen = {email}
        if place:
            siblings = session.scalars(select(Lead).where(Lead.place_id == place)).all()
            for other in siblings:
                other_email = normalize_email(other.contact_email or "")
                if not other_email or other_email in seen:
                    continue
                seen.add(other_email)
                rows.append(
                    _store(
                        repo,
                        "email",
                        other_email,
                        channel=channel,
                        reason=reason,
                        detail=None,
                        keep_text=False,
                    )
                )
    elif host:
        rows.append(
            _store(
                repo,
                "domain",
                host,
                channel=channel,
                reason=reason,
                detail=None,
                keep_text=False,
            )
        )
    return rows


def erase_personal_data(session: Session, lead: Lead) -> None:
    """Borra el detalle personal. La fila de supresión, por hash, queda."""
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
    for message in session.scalars(select(Message).where(Message.lead_id == lead.id)):
        message.body_text = ""
        message.body_html = None
        message.subject = None
        message.check_result = None
    for event in session.scalars(select(Event).where(Event.lead_id == lead.id)):
        event.meta = None
        event.message = ""
    for approval in session.scalars(select(Approval).where(Approval.lead_id == lead.id)):
        approval.payload = {}
        approval.decision_note = None
    for artifact in session.scalars(select(Artifact).where(Artifact.lead_id == lead.id)):
        artifact.meta = None
        artifact.path = ""
    lead.business = "anonimizado"
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
