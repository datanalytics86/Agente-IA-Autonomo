"""Capa 1 del Checker: reglas deterministas, sin red y sin LLM.

No abre sockets, no lee el entorno y no envía mensajes. El juez LLM es otra capa.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel

# Invisibles, guion blando y marcas bidireccionales no deben partir una palabra.
_INVISIBLE_RE = re.compile(
    r"[\u00ad\u200b-\u200f\u2060\u2066-\u2069\u202a-\u202e\ufeff]"
)
_KINDS = frozenset({"email", "domain", "phone", "instagram", "linkedin"})

# El punto es separador de miles en es-CL. Por debajo de 100.000 no se trata
# como precio salvo que venga marcado con $, CLP o pesos.
_PRICE_MARKED_RE = re.compile(
    r"(?i)(?:\$\s*)(\d{1,3}(?:\.\d{3})+|\d{4,8})(?!\d)"
    r"|(\d{1,3}(?:\.\d{3})+|\d{4,8})(?!\d)\s*(?:clp|pesos)"
)
_PRICE_DOTTED_RE = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{3})+)(?!\d)")
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?56[\s.\-]*)?9[\s.\-]*\d{4}[\s.\-]*\d{4}(?!\d)"
)
_URL_RE = re.compile(r"(?i)(?:https?://[^\s<>\"']+|//[^\s<>\"']+)")
_OPT_OUT_PHRASES = (
    "no me escriban",
    "no me escribas",
    "dejame de escribir",
    "no me contacten",
)
_OPT_OUT_RE = re.compile(r"\b(?:stop|baja|unsubscribe[d]?|remove me)\b")
_FORBIDDEN: tuple[tuple[str, str], ...] = (
    (r"\bgarantizad[oa]s?\b", "garantizado"),
    ("resultados asegurados", "resultados asegurados"),
    ("cliente local (ejemplo", "cliente local (ejemplo"),
    ("100%", "100%"),
    ("ultimas unidades", "últimas unidades"),
    ("acto seguido te llamamos", "acto seguido te llamamos"),
)
_TESTIMONIAL = (
    "testimonio",
    "testimonios",
    "clientes dicen",
    "cliente nos dijo",
    "cliente nos conto",
    "caso de exito",
    "cliente satisfecho",
    "ejemplo de tono",
)
_INJECTION_RES = (
    re.compile(r"\bignor(?:a|e|ar|en|ad)\b.{0,80}\binstrucciones\b"),
    re.compile(r"\bignore\b.{0,80}\binstructions\b"),
    re.compile(r"\bolvida\b.{0,60}\binstrucciones\b"),
    re.compile(r"\bdisregard\b.{0,40}\binstructions\b"),
    re.compile(
        r"\b(?:cambia(?:r)?|modifica(?:r)?|actualiza(?:r)?)\b.{0,60}\b"
        r"estado\b.{0,30}\b(?:del\s+)?lead\b"
    ),
    re.compile(r"\blead\.status\b"),
    re.compile(
        r"\bchange\b.{0,40}\b(?:the\s+)?"
        r"(?:lead\s+status|status\s+of\s+the\s+lead)\b"
    ),
    re.compile(
        r"\b(?:revela|muestra|show|reveal)(?:r|me)?\b.{0,40}\b"
        r"(?:system prompt|prompt del sistema|prompt de sistema)\b"
    ),
    re.compile(r"\bsystem prompt\b"),
    re.compile(r"\bprompt del sistema\b"),
    re.compile(r"\benvia(?:r|le|me|n)?\b.{0,40}\bpitch\b.{0,30}\ba\b"),
    re.compile(
        r"\benvia(?:r|le|me|n)?\b.{0,40}\b(?:mensaje|correo|mail)\b.{0,30}\b"
        r"(?:a un tercero|a terceros|a x)\b"
    ),
    re.compile(r"\bsend\b.{0,40}\b(?:pitch|message|email)\b.{0,25}\bto\b"),
)
_CHANNEL_LIMITS = (
    ("email", 1200),
    ("instagram", 500),
    ("linkedin", 500),
    ("whatsapp", 400),
)


class CheckResult(BaseModel):
    approved: bool
    score: int
    reasons: list[str]


@dataclass
class Message:
    body: str = ""
    channel: str = ""
    direction: str = "out"
    suppressed: bool | None = None
    recipient_suppressed: bool | None = None
    subject: str = ""
    body_html: str = ""


@dataclass
class Lead:
    contact_email: str | None = None
    phone_public: str | None = None
    instagram_handle: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    business: str = ""
    consent: Any = None
    whatsapp_consent: bool = False
    emails: tuple[str, ...] | list[str] = ()
    phones: tuple[str, ...] | list[str] = ()


@dataclass
class Settings:
    agency_name: str = ""
    price_min_clp: int | None = 250_000
    price_max_clp: int | None = 450_000
    public_base_url: str = ""
    agency_email: str = ""
    agency_phone: str = ""


def _fold(text: str) -> str:
    cleaned = _INVISIBLE_RE.sub("", text or "")
    nfkd = unicodedata.normalize("NFKD", cleaned)
    without = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without.lower()).strip()


def is_opt_out(text: str) -> bool:
    """True si el texto pide la baja, con o sin mayúsculas y con o sin tildes."""
    folded = _fold(text)
    if not folded:
        return False
    if any(phrase in folded for phrase in _OPT_OUT_PHRASES):
        return True
    return _OPT_OUT_RE.search(folded) is not None


def _kind(kind: str) -> str:
    normalized = (kind or "").strip().lower()
    if normalized not in _KINDS:
        allowed = ", ".join(sorted(_KINDS))
        raise ValueError(f"kind desconocido: {kind!r}. Use {allowed}.")
    return normalized


def normalize_contact(kind: str, value: str) -> str:
    """Normaliza un contacto antes de hashearlo. No consulta la red."""
    selected = _kind(kind)
    raw = (value or "").strip()
    if selected == "email":
        return raw.lower()
    if selected == "domain":
        return _domain_host(raw)
    if selected == "phone":
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("9") and len(digits) == 9:
            digits = "56" + digits
        return digits
    if selected == "instagram":
        return raw.lstrip("@").lower()
    lowered = re.sub(r"^https?://", "", raw.lower())
    lowered = re.sub(r"^www\.", "", lowered)
    return lowered.strip("/")


def _domain_host(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"http://{raw}"
    host = urlparse(candidate).hostname or ""
    return host.removeprefix("www.")


def suppression_hash(kind: str, value: str) -> str:
    """SHA-256 hex del valor ya normalizado. El kind no entra al hash."""
    normalized = normalize_contact(kind, value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace("_", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")
    if re.fullmatch(r"\d+", text):
        return int(text)
    return None


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value if item)


def _coerce_message(message: Message | Mapping[str, Any]) -> Message:
    if isinstance(message, Message):
        return message
    body = message.get("body")
    if body is None:
        body = message.get("body_text") or ""
    return Message(
        body=str(body or ""),
        channel=str(message.get("channel") or ""),
        direction=str(message.get("direction") or "out"),
        suppressed=message.get("suppressed"),
        recipient_suppressed=message.get("recipient_suppressed"),
        subject=str(message.get("subject") or ""),
        body_html=str(message.get("body_html") or ""),
    )


def _coerce_lead(lead: Lead | Mapping[str, Any] | None) -> Lead:
    if lead is None:
        return Lead()
    if isinstance(lead, Lead):
        return lead
    return Lead(
        contact_email=lead.get("contact_email"),
        phone_public=lead.get("phone_public"),
        instagram_handle=lead.get("instagram_handle"),
        linkedin_url=lead.get("linkedin_url"),
        website_url=lead.get("website_url"),
        business=str(lead.get("business") or ""),
        consent=lead.get("consent"),
        whatsapp_consent=bool(lead.get("whatsapp_consent") or False),
        emails=_as_str_tuple(lead.get("emails")),
        phones=_as_str_tuple(lead.get("phones")),
    )


def _coerce_settings(settings: Settings | Mapping[str, Any] | None) -> Settings:
    if settings is None:
        return Settings()
    if isinstance(settings, Settings):
        return settings
    present = set(settings)
    return Settings(
        agency_name=str(settings.get("agency_name") or ""),
        price_min_clp=(
            _as_int(settings.get("price_min_clp"))
            if "price_min_clp" in present
            else 250_000
        ),
        price_max_clp=(
            _as_int(settings.get("price_max_clp"))
            if "price_max_clp" in present
            else 450_000
        ),
        public_base_url=str(settings.get("public_base_url") or ""),
        agency_email=str(settings.get("agency_email") or ""),
        agency_phone=str(settings.get("agency_phone") or ""),
    )


def _digits_to_int(text: str) -> int | None:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        return int(text.replace(".", ""))
    if re.fullmatch(r"\d+", text):
        return int(text)
    return None


def _prices_clp(text: str) -> list[int]:
    found: list[int] = []
    seen: set[int] = set()

    def add(raw: str | None) -> None:
        if not raw:
            return
        amount = _digits_to_int(raw)
        if amount is None or amount in seen:
            return
        seen.add(amount)
        found.append(amount)

    for match in _PRICE_MARKED_RE.finditer(text):
        add(match.group(1) or match.group(2))
    for match in _PRICE_DOTTED_RE.finditer(text):
        amount = _digits_to_int(match.group(1))
        if amount is not None and amount >= 100_000:
            add(match.group(1))
    return found


def _clean_url(url: str) -> str:
    return url.rstrip(".,);:]}>\"'")


def _iter_urls(text: str) -> list[str]:
    return [_clean_url(match.group(0)) for match in _URL_RE.finditer(text)]


def _host_of(url: str) -> str:
    candidate = url
    if candidate.startswith("//"):
        candidate = f"https:{candidate}"
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    host = (urlparse(candidate).hostname or "").lower()
    return host.removeprefix("www.")


def _own_host(url: str, public_base_url: str) -> bool:
    base = _host_of(public_base_url) if public_base_url else ""
    host = _host_of(url)
    if not base or not host:
        return False
    return host == base or host.endswith(f".{base}")


def _channel_limit(channel: str) -> int | None:
    folded = (channel or "").strip().lower()
    for name, limit in _CHANNEL_LIMITS:
        if name in folded:
            return limit
    return None


def _is_outbound(direction: str) -> bool:
    return (direction or "out").strip().lower() in {"out", "outbound", "salida"}


def _has_whatsapp_consent(lead: Lead) -> bool:
    if lead.whatsapp_consent:
        return True
    consent = lead.consent
    if isinstance(consent, str):
        folded = _fold(consent)
        return "whatsapp" in folded
    if not isinstance(consent, dict):
        return False
    if consent.get("whatsapp") is True:
        return True
    channels = consent.get("channels") or consent.get("canales") or []
    if isinstance(channels, str):
        channels = [channels]
    if any(str(item).strip().lower() == "whatsapp" for item in channels):
        return True
    kind = str(consent.get("type") or consent.get("tipo") or "").strip().lower()
    return kind in {"whatsapp", "whatsapp_opt_in", "opt_in_whatsapp"}


def _email_has_baja(text: str) -> bool:
    folded = _fold(text)
    if re.search(r"\bbaja\b", folded):
        return True
    for url in _iter_urls(text):
        target = _fold(url)
        if any(token in target for token in ("baja", "unsubscribe", "opt-out", "optout")):
            return True
    return bool(re.search(r"(?:^|[\s\"'(=/])/?baja\b", folded))


def _known_emails(lead: Lead, settings: Settings) -> set[str]:
    values: list[Any] = [lead.contact_email, settings.agency_email, *lead.emails]
    return {normalize_contact("email", str(value)) for value in values if value}


def _known_phones(lead: Lead, settings: Settings) -> set[str]:
    values: list[Any] = [lead.phone_public, settings.agency_phone, *lead.phones]
    return {
        normalize_contact("phone", str(value))
        for value in values
        if value and normalize_contact("phone", str(value))
    }


def _spam_reasons(text: str) -> list[str]:
    reasons: list[str] = []
    # «!!!» ya es spam: tres o más signos.
    if text.count("!") >= 3:
        reasons.append("heurística de spam: demasiados signos de exclamación")
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) >= 20:
        upper = sum(1 for ch in letters if ch.isupper())
        if upper / len(letters) > 0.30:
            reasons.append("heurística de spam: exceso de mayúsculas")
    return reasons


def _score(reasons: list[str]) -> int:
    if not reasons:
        return 100
    return max(0, 100 - 20 * len(reasons))


def check_rules(
    message: Message | Mapping[str, Any],
    lead: Lead | Mapping[str, Any] | None = None,
    settings: Settings | Mapping[str, Any] | None = None,
) -> CheckResult:
    """Revisa un mensaje. Aprueba solo si no hay ninguna razón de rechazo."""
    msg = _coerce_message(message)
    current_lead = _coerce_lead(lead)
    current_settings = _coerce_settings(settings)
    # El asunto no acredita opt-out, identidad ni baja: eso va en el cuerpo.
    # Igual se revisa, porque por el asunto se cuelan enlaces, precios y frases.
    body_parts = [part for part in (msg.body, msg.body_html) if part.strip()]
    body_text = "\n".join(body_parts)
    scanned_parts = list(body_parts)
    if msg.subject.strip():
        scanned_parts.append(msg.subject)
    scanned = "\n".join(scanned_parts)
    body_folded = _fold(body_text)
    scanned_folded = _fold(scanned)
    reasons: list[str] = []

    agency = current_settings.agency_name.strip()
    if not agency:
        reasons.append("falta identidad de la agencia")
    elif _fold(agency) not in body_folded:
        reasons.append("el cuerpo no incluye el nombre de la agencia")

    if not is_opt_out(body_text):
        reasons.append("falta opt-out en el cuerpo")

    if "email" in msg.channel.lower() and not _email_has_baja(body_text):
        reasons.append("email sin indicación de baja")

    if msg.suppressed is True or msg.recipient_suppressed is True:
        reasons.append("destinatario suprimido")

    known_emails = _known_emails(current_lead, current_settings)
    seen_emails: set[str] = set()
    for found in _EMAIL_RE.findall(scanned):
        normalized = normalize_contact("email", found)
        if normalized in seen_emails or normalized in known_emails:
            seen_emails.add(normalized)
            continue
        seen_emails.add(normalized)
        reasons.append(f"contacto inventado: email {normalized}")

    known_phones = _known_phones(current_lead, current_settings)
    seen_phones: set[str] = set()
    for found in _PHONE_RE.findall(scanned):
        normalized = normalize_contact("phone", found)
        if not normalized or normalized in seen_phones or normalized in known_phones:
            seen_phones.add(normalized)
            continue
        seen_phones.add(normalized)
        reasons.append(f"contacto inventado: teléfono {normalized}")

    prices = _prices_clp(scanned)
    low = current_settings.price_min_clp
    high = current_settings.price_max_clp
    if prices and (
        low is None
        or high is None
        or low > high
        or any(price < low or price > high for price in prices)
    ):
        reasons.append("precio fuera de banda; requiere HITL")

    for needle, label in _FORBIDDEN:
        if needle.startswith("\\"):
            hit = re.search(needle, scanned_folded) is not None
        else:
            hit = needle in scanned_folded
        if hit:
            reasons.append(f"frase prohibida: {label}")

    if any(token in scanned_folded for token in _TESTIMONIAL):
        reasons.append("testimonio inventado")

    limit = _channel_limit(msg.channel)
    longest = max((len(part) for part in (msg.body, msg.body_html)), default=0)
    if limit is not None and longest > limit:
        reasons.append(f"largo excedido para {msg.channel.strip().lower()}")

    if (
        "whatsapp" in msg.channel.lower()
        and _is_outbound(msg.direction)
        and not _has_whatsapp_consent(current_lead)
    ):
        reasons.append("whatsapp en frío sin consentimiento")

    seen_urls: set[str] = set()
    for url in _iter_urls(scanned):
        if url in seen_urls or _own_host(url, current_settings.public_base_url):
            seen_urls.add(url)
            continue
        seen_urls.add(url)
        reasons.append(f"enlace externo no permitido: {url}")

    spam_seen: set[str] = set()
    for part in scanned_parts:
        for reason in _spam_reasons(part):
            if reason not in spam_seen:
                spam_seen.add(reason)
                reasons.append(reason)

    if looks_like_injection(scanned):
        reasons.append("posible inyección de instrucciones")

    return CheckResult(approved=not reasons, score=_score(reasons), reasons=reasons)


def looks_like_injection(text: str) -> bool:
    """True si un texto no confiable pide desobedecer al sistema.

    Cubre: ignorar instrucciones, cambiar el estado del lead, revelar el
    system prompt, o enviar un mensaje a un tercero.
    """
    folded = _fold(text)
    if not folded:
        return False
    return any(pattern.search(folded) for pattern in _INJECTION_RES)
