"""Agenda Cal.com (default) y Calendly. La firma se verifica sobre el body crudo."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote, urlsplit, urlunsplit

from pydantic import BaseModel

from core.config import Settings
from integrations.errors import WebhookSignatureError
from integrations.headers import header

_CAL_HEADER = "x-cal-signature-256"
_CALENDLY_HEADER = "calendly-webhook-signature"
_TOLERANCE_S = 180


class BookingEvent(BaseModel):
    lead_id: str
    start: datetime
    provider_event_id: str
    provider: str


class BookingProvider(Protocol):
    def link_for(self, lead_id: str) -> str: ...

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> BookingEvent: ...


def _eq(expected: str, presented: str) -> bool:
    left = expected.encode()
    right = presented.strip().encode()
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _signature_hex(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_calcom_signature(body: bytes, signature: str, secret: str) -> None:
    if not secret or not signature:
        raise WebhookSignatureError("firma cal.com ausente")
    presented = signature.strip()
    if presented.lower().startswith("sha256="):
        presented = presented.split("=", 1)[1].strip()
    if not _eq(_signature_hex(secret, body), presented):
        raise WebhookSignatureError("firma cal.com inválida")


def verify_calendly_signature(
    body: bytes,
    signature: str,
    secret: str,
    *,
    now: datetime | None = None,
    tolerance_s: int = _TOLERANCE_S,
) -> None:
    if not secret or not signature:
        raise WebhookSignatureError("firma calendly ausente")
    parts: dict[str, str] = {}
    for piece in signature.split(","):
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        parts[key.strip()] = value.strip()
    ts = parts.get("t", "")
    presented = parts.get("v1", "")
    if not ts or not presented:
        raise WebhookSignatureError("firma calendly incompleta")
    try:
        stamp = int(ts)
    except ValueError as exc:
        raise WebhookSignatureError("timestamp calendly inválido") from exc
    current = int((now or datetime.now(UTC)).timestamp())
    if abs(current - stamp) > tolerance_s:
        raise WebhookSignatureError("timestamp calendly fuera de tolerancia")
    expected = _signature_hex(secret, f"{ts}.".encode() + body)
    if not _eq(expected, presented):
        raise WebhookSignatureError("firma calendly inválida")


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("value", "answer"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


def _lead_from(data: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        found = _text(data.get(key))
        if found:
            return found
    return ""


def parse_start(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("el webhook no trae inicio")
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _loads(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("webhook de agenda no es JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("webhook de agenda no es un objeto")
    return payload


def _require_event(
    lead_id: str,
    start: datetime | None,
    event_id: str,
    provider: str,
) -> BookingEvent:
    if not lead_id:
        raise ValueError("el webhook no trae lead_id")
    if start is None or not event_id:
        raise ValueError("el webhook no trae la cita")
    return BookingEvent(
        lead_id=lead_id,
        start=start,
        provider_event_id=event_id,
        provider=provider,
    )


def _append_query(base: str, extra: str) -> str:
    root = base.strip() or "https://booking.invalid/cita"
    parts = urlsplit(root)
    query = parts.query
    if extra:
        query = f"{query}&{extra}" if query else extra
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _require_lead(lead_id: str) -> str:
    cleaned = lead_id.strip()
    if not cleaned:
        raise ValueError("lead_id vacío")
    return cleaned


class CalComBooking:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def link_for(self, lead_id: str) -> str:
        lead = _require_lead(lead_id)
        return _append_query(
            self.settings.booking_link,
            f"metadata[lead_id]={quote(lead, safe='')}",
        )

    def poll(self) -> list[BookingEvent]:
        """Las citas reales llegan por webhook. Este sondeo no abre sockets."""
        return []

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> BookingEvent:
        verify_calcom_signature(
            body,
            header(headers, _CAL_HEADER),
            self.settings.calcom_webhook_secret,
        )
        payload = _loads(body)
        inner = _mapping(payload.get("payload"))
        lead = ""
        for source in (
            _mapping(inner.get("metadata")),
            _mapping(inner.get("responses")),
            _mapping(inner.get("userFieldsResponses")),
            _mapping(inner.get("bookingFieldsResponses")),
            _mapping(payload.get("metadata")),
        ):
            lead = _lead_from(source, ("lead_id", "utm_content"))
            if lead:
                break
        start_raw = inner.get("startTime") or inner.get("start")
        event_id = str(inner.get("uid") or inner.get("bookingId") or "")
        start = parse_start(start_raw) if start_raw else None
        return _require_event(lead, start, event_id, "calcom")


class CalendlyBooking:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def link_for(self, lead_id: str) -> str:
        lead = _require_lead(lead_id)
        return _append_query(self.settings.booking_link, f"utm_content={quote(lead, safe='')}")

    def poll(self) -> list[BookingEvent]:
        """Las citas reales llegan por webhook. Este sondeo no abre sockets."""
        return []

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> BookingEvent:
        verify_calendly_signature(
            body,
            header(headers, _CALENDLY_HEADER),
            self.settings.calendly_webhook_signing_key,
        )
        payload = _loads(body)
        inner = _mapping(payload.get("payload"))
        lead = _lead_from(_mapping(inner.get("tracking")), ("utm_content", "lead_id"))
        if not lead:
            answers = inner.get("questions_and_answers")
            if isinstance(answers, list):
                for item in answers:
                    if not isinstance(item, dict):
                        continue
                    question = str(item.get("question") or "").strip().lower()
                    if question in {"lead_id", "lead id"}:
                        lead = _text(item.get("answer"))
                        if lead:
                            break
        if not lead:
            lead = _text(inner.get("lead_id"))
        scheduled = _mapping(inner.get("scheduled_event"))
        event_id = str(inner.get("uri") or scheduled.get("uri") or "")
        start_raw = scheduled.get("start_time") or inner.get("start_time")
        start = parse_start(start_raw) if start_raw else None
        return _require_event(lead, start, event_id, "calendly")


class FakeBooking:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def link_for(self, lead_id: str) -> str:
        lead = _require_lead(lead_id)
        return _append_query(self.settings.booking_link, f"lead_id={quote(lead, safe='')}")

    def poll(self) -> list[BookingEvent]:
        return []

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> BookingEvent:
        del headers
        payload = _loads(body)
        start_raw = payload.get("start")
        start = parse_start(start_raw) if start_raw else None
        return _require_event(
            _text(payload.get("lead_id")),
            start,
            str(payload.get("provider_event_id") or ""),
            "fake",
        )


def build_booking(settings: Settings) -> BookingProvider:
    if settings.app_mode == "demo" or settings.dry_run:
        return FakeBooking(settings)
    if settings.booking_provider == "calendly":
        if not settings.calendly_webhook_signing_key:
            return FakeBooking(settings)
        return CalendlyBooking(settings)
    if not settings.calcom_webhook_secret:
        return FakeBooking(settings)
    return CalComBooking(settings)
