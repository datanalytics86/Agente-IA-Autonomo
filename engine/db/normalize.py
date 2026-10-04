"""Normalización de contactos y nombres. El hash no guarda el valor crudo."""

from __future__ import annotations

import hashlib
import re
import unicodedata

CONTACT_KINDS = frozenset({"email", "domain", "instagram", "linkedin", "phone"})

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://")


def normalize_business(name: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.lower().split())


def normalize_contact(kind: str, raw_value: str) -> str:
    if kind not in CONTACT_KINDS:
        raise ValueError(f"kind de supresión desconocido: {kind}")
    if kind == "email":
        return raw_value.strip().lower()
    if kind == "domain":
        return _normalize_domain(raw_value)
    if kind == "instagram":
        return raw_value.strip().lstrip("@").lower()
    if kind == "linkedin":
        value = _strip_scheme(raw_value.strip().lower()).rstrip("/")
        if value.startswith("www."):
            return value[4:]
        return value
    return _normalize_phone(raw_value)


def contact_hash(kind: str, raw_value: str) -> str:
    normalized = normalize_contact(kind, raw_value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _strip_scheme(value: str) -> str:
    return _SCHEME.sub("", value.strip().lower())


def _normalize_domain(raw_value: str) -> str:
    value = _strip_scheme(raw_value)
    value = value.split("/")[0].split("?")[0].split("#")[0]
    if "@" in value:
        value = value.split("@", 1)[1]
    if value.startswith("www."):
        value = value[4:]
    return value.rstrip(".")


def _normalize_phone(raw_value: str) -> str:
    digits = re.sub(r"\D", "", raw_value)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("56"):
        return digits
    if digits.startswith("0"):
        digits = digits.lstrip("0")
    return f"56{digits}"
