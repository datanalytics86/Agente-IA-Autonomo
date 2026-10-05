"""Agenda: firma de Cal.com y Calendly, y lead_id en el evento."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any

import pytest

from core.config import Settings
from integrations.booking import (
    CalComBooking,
    CalendlyBooking,
    FakeBooking,
    build_booking,
    verify_calendly_signature,
)
from integrations.errors import WebhookSignatureError


def _settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_mode": "prod",
        "dry_run": False,
        "secret_key": "s" * 32,
        "database_url": "sqlite:///:memory:",
        "admin_email": "admin@example.com",
        "admin_password_hash": "hash-de-prueba",
        "public_base_url": "https://agencia.example",
        "agency_name": "Agencia Test",
        "agency_email": "agencia@example.com",
        "booking_provider": "calcom",
        "booking_link": "https://cal.example/demo?utm_source=agencia",
        "calcom_webhook_secret": "cal-secret",
        "calendly_webhook_signing_key": "calendly-secret",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def _sign_calcom(body: bytes, secret: str = "cal-secret") -> dict[str, str]:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Cal-Signature-256": digest}


def _sign_calendly(
    body: bytes,
    secret: str = "calendly-secret",
    ts: str | None = None,
) -> dict[str, str]:
    stamp = ts or str(int(time.time()))
    digest = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return {"Calendly-Webhook-Signature": f"t={stamp},v1={digest}"}


def test_calcom_lee_lead_id_de_metadata_y_utm() -> None:
    provider = CalComBooking(_settings())
    metadata = {
        "triggerEvent": "BOOKING_CREATED",
        "payload": {
            "uid": "bk_1",
            "startTime": "2026-10-05T15:00:00Z",
            "metadata": {"lead_id": "lead-1"},
        },
    }
    body = json.dumps(metadata).encode()
    event = provider.parse_webhook(body, _sign_calcom(body))
    assert event.lead_id == "lead-1"
    assert event.provider_event_id == "bk_1"
    assert event.provider == "calcom"
    assert event.start == datetime(2026, 10, 5, 15, 0, tzinfo=UTC)

    utm = {
        "triggerEvent": "BOOKING_CREATED",
        "payload": {
            "uid": "bk_2",
            "startTime": "2026-10-06T12:30:00Z",
            "metadata": {"utm_content": "lead-utm"},
        },
    }
    raw = json.dumps(utm).encode()
    parsed = provider.parse_webhook(raw, _sign_calcom(raw))
    assert parsed.lead_id == "lead-utm"
    assert parsed.provider_event_id == "bk_2"


def test_calcom_firma_mala_lanza() -> None:
    provider = CalComBooking(_settings())
    body = b'{"payload":{"uid":"x","startTime":"2026-10-05T15:00:00Z","metadata":{"lead_id":"l"}}}'
    with pytest.raises(WebhookSignatureError):
        provider.parse_webhook(body, {"X-Cal-Signature-256": "deadbeef"})
    with pytest.raises(WebhookSignatureError):
        provider.parse_webhook(b"no-json", {"X-Cal-Signature-256": "00"})


def test_calcom_sin_lead_id_lanza() -> None:
    provider = CalComBooking(_settings())
    body = json.dumps(
        {"payload": {"uid": "bk", "startTime": "2026-10-05T15:00:00Z", "metadata": {}}}
    ).encode()
    with pytest.raises(ValueError, match="lead_id"):
        provider.parse_webhook(body, _sign_calcom(body))


def test_calendly_lee_utm_y_pregunta() -> None:
    provider = CalendlyBooking(_settings(booking_provider="calendly"))
    payload = {
        "event": "invitee.created",
        "payload": {
            "uri": "https://api.calendly.com/scheduled_events/evt/invitees/inv",
            "tracking": {"utm_content": "lead-cal"},
            "scheduled_event": {
                "uri": "https://api.calendly.com/scheduled_events/evt",
                "start_time": "2026-10-07T18:00:00Z",
            },
        },
    }
    body = json.dumps(payload).encode()
    event = provider.parse_webhook(body, _sign_calendly(body))
    assert event.lead_id == "lead-cal"
    assert event.provider == "calendly"
    assert event.provider_event_id.endswith("/inv")
    assert event.start == datetime(2026, 10, 7, 18, 0, tzinfo=UTC)

    asked = {
        "payload": {
            "uri": "https://api.calendly.com/invitees/inv-2",
            "questions_and_answers": [{"question": "lead_id", "answer": "lead-qa"}],
            "scheduled_event": {"start_time": "2026-10-08T18:00:00Z"},
        }
    }
    raw = json.dumps(asked).encode()
    parsed = provider.parse_webhook(raw, _sign_calendly(raw))
    assert parsed.lead_id == "lead-qa"


def test_calendly_firma_mala_o_vieja_lanza() -> None:
    provider = CalendlyBooking(_settings())
    body = json.dumps(
        {
            "payload": {
                "uri": "https://api.calendly.com/invitees/x",
                "tracking": {"utm_content": "lead"},
                "scheduled_event": {"start_time": "2026-10-07T18:00:00Z"},
            }
        }
    ).encode()
    with pytest.raises(WebhookSignatureError):
        provider.parse_webhook(body, {"Calendly-Webhook-Signature": "t=1,v1=dead"})

    now = datetime(2026, 10, 4, 15, 0, tzinfo=UTC)
    old = str(int(now.timestamp()) - 600)
    stale = _sign_calendly(body, ts=old)["Calendly-Webhook-Signature"]
    with pytest.raises(WebhookSignatureError):
        verify_calendly_signature(body, stale, "calendly-secret", now=now)


def test_links_llevan_lead_id() -> None:
    assert "metadata[lead_id]=lead-1" in CalComBooking(_settings()).link_for("lead-1")
    assert "utm_source=agencia" in CalComBooking(_settings()).link_for("lead-1")
    assert "utm_content=lead-1" in CalendlyBooking(_settings()).link_for("lead-1")
    assert "lead_id=lead-1" in FakeBooking(_settings()).link_for("lead-1")
    with pytest.raises(ValueError):
        CalComBooking(_settings()).link_for("  ")


def test_fabrica_demo_o_sin_secreto_es_fake() -> None:
    assert isinstance(build_booking(_settings(app_mode="demo", dry_run=True)), FakeBooking)
    assert isinstance(build_booking(_settings(calcom_webhook_secret="")), FakeBooking)
    assert isinstance(build_booking(_settings()), CalComBooking)
    calendly = build_booking(_settings(booking_provider="calendly"))
    assert isinstance(calendly, CalendlyBooking)
    assert isinstance(
        build_booking(_settings(booking_provider="calendly", calendly_webhook_signing_key="")),
        FakeBooking,
    )
