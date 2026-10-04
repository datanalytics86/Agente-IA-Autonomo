"""Mercado Pago: la firma falla si no calza y el webhook no marca pagado."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest

from core.config import Settings
from integrations.errors import ProviderRequestError, WebhookSignatureError
from integrations.payments import (
    FakePaymentProvider,
    MercadoPagoProvider,
    PaymentFact,
    build_payments,
    verify_mp_signature,
)
from integrations.payments.base import MP_API


def _settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_mode": "prod",
        "dry_run": False,
        "mp_access_token": "TEST-MP",
        "mp_webhook_secret": "mp-secret",
        "public_base_url": "https://agencia.example",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def _sign(
    data_id: str,
    request_id: str = "req-1",
    ts: str = "1700000000",
    secret: str = "mp-secret",
) -> str:
    signed = data_id.lower() if any(char.isalpha() for char in data_id) else data_id
    manifest = f"id:{signed};request-id:{request_id};ts:{ts};"
    digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={digest}"


def _headers(data_id: str) -> dict[str, str]:
    return {"x-signature": _sign(data_id), "x-request-id": "req-1"}


def test_verify_mp_signature_falla_si_el_header_no_calza() -> None:
    verify_mp_signature(
        secret="mp-secret",
        x_signature=_sign("999"),
        x_request_id="req-1",
        data_id="999",
    )
    verify_mp_signature(
        secret="mp-secret",
        x_signature=_sign("AbC12"),
        x_request_id="req-1",
        data_id="AbC12",
    )
    with pytest.raises(WebhookSignatureError):
        verify_mp_signature(
            secret="mp-secret",
            x_signature="ts=1700000000,v1=deadbeef",
            x_request_id="req-1",
            data_id="999",
        )
    with pytest.raises(WebhookSignatureError):
        verify_mp_signature(secret="mp-secret", x_signature="", x_request_id="req-1", data_id="999")


def test_parse_webhook_no_marca_pagado(respx_mock: Any) -> None:
    route = respx_mock.route().respond(200, json={"status": "approved", "id": "999"})
    provider = MercadoPagoProvider(_settings())
    body = json.dumps(
        {
            "action": "payment.updated",
            "type": "payment",
            "id": "notif-1",
            "status": "approved",
            "data": {"id": "999"},
        }
    ).encode()
    assert provider.parse_webhook(body, _headers("999")) == "999"
    assert route.call_count == 0
    with pytest.raises(WebhookSignatureError):
        provider.parse_webhook(body, {"x-signature": "ts=1,v1=no", "x-request-id": "req-1"})
    assert route.call_count == 0


def test_create_preference_y_fetch_idempotente(respx_mock: Any) -> None:
    created = respx_mock.post(f"{MP_API}/checkout/preferences").respond(
        201,
        json={
            "id": "pref-1",
            "init_point": "https://www.mercadopago.cl/checkout/v1/redirect?pref_id=pref-1",
        },
    )
    payment = {
        "id": 999,
        "status": "approved",
        "transaction_amount": 175000,
        "external_reference": "ord-1",
    }
    fetched = respx_mock.get(f"{MP_API}/v1/payments/999").respond(200, json=payment)
    provider = MercadoPagoProvider(_settings())
    preference = provider.create_preference("ord-1", "Landing", 175000)
    assert preference.preference_id == "pref-1"
    assert preference.order_id == "ord-1"
    assert preference.amount_clp == 175000
    sent = json.loads(created.calls.last.request.content.decode())
    assert sent["external_reference"] == "ord-1"
    assert sent["items"][0]["unit_price"] == 175000
    assert sent["items"][0]["currency_id"] == "CLP"
    assert sent["notification_url"] == "https://agencia.example/webhooks/mercadopago"
    assert created.calls.last.request.headers["Authorization"] == "Bearer TEST-MP"
    assert created.calls.last.request.headers["X-Idempotency-Key"] == "ord-1"

    first = provider.fetch_payment("999")
    second = provider.fetch_payment("999")
    assert first == second
    assert first == PaymentFact(
        provider_payment_id="999",
        status="approved",
        amount_clp=175000,
        order_id="ord-1",
        approved=True,
    )
    assert fetched.call_count == 2


def test_fetch_pendiente_no_queda_approved(respx_mock: Any) -> None:
    respx_mock.get(f"{MP_API}/v1/payments/42").respond(
        200,
        json={
            "id": "42",
            "status": "pending",
            "transaction_amount": 1000,
            "external_reference": "ord-2",
        },
    )
    fact = MercadoPagoProvider(_settings()).fetch_payment("42")
    assert fact.approved is False
    assert fact.status == "pending"
    assert fact.provider_payment_id == "42"


def test_dry_run_no_llama_a_mercado_pago(respx_mock: Any) -> None:
    route = respx_mock.route().respond(200, json={"id": "x"})
    provider = MercadoPagoProvider(_settings(dry_run=True))
    with pytest.raises(ProviderRequestError):
        provider.create_preference("ord-1", "Landing", 175000)
    with pytest.raises(ProviderRequestError):
        provider.fetch_payment("999")
    assert route.call_count == 0


def test_fabrica_y_fake_no_marcan_pagado(respx_mock: Any) -> None:
    route = respx_mock.route().respond(200, json={"status": "approved"})
    fake = build_payments(_settings(app_mode="demo", dry_run=True, mp_access_token=""))
    assert isinstance(fake, FakePaymentProvider)
    body = json.dumps({"status": "approved", "data": {"id": "999"}}).encode()
    assert fake.parse_webhook(body, {}) == "999"
    assert fake.fetch_payment("999").approved is False
    assert fake.fetch_payment("999") == fake.fetch_payment("999")
    preference = fake.create_preference("ord-1", "Landing", 175000)
    assert preference.checkout_url.startswith("https://pay.invalid/")
    assert route.call_count == 0
    assert isinstance(build_payments(_settings()), MercadoPagoProvider)
    assert isinstance(build_payments(_settings(mp_access_token="")), FakePaymentProvider)
