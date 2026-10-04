"""Meta: firma, respuesta solo con ventana, y cero envíos en frío."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest

from core.config import Settings
from integrations.errors import WebhookSignatureError
from integrations.meta import (
    GRAPH_VERSION,
    FakeMeta,
    MetaCloud,
    build_meta,
    cold_channel_result,
)
from integrations.meta.base import GRAPH


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
        "meta_app_secret": "app-secret",
        "meta_verify_token": "verify-token",
        "ig_access_token": "ig-test",
        "whatsapp_token": "wa-test",
        "whatsapp_phone_number_id": "12345",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def _sign(body: bytes, secret: str = "app-secret") -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_subscription() -> None:
    client = MetaCloud(_settings())
    assert client.verify_subscription("subscribe", "verify-token", "123") == "123"
    assert client.verify_subscription("subscribe", "otro", "123") is None
    assert client.verify_subscription("denied", "verify-token", "123") is None
    assert FakeMeta(_settings()).verify_subscription("subscribe", "verify-token", "9") == "9"


def test_parse_instagram_y_whatsapp() -> None:
    client = MetaCloud(_settings())
    instagram = {
        "object": "instagram",
        "entry": [
            {
                "id": "page",
                "messaging": [
                    {
                        "sender": {"id": "user-1"},
                        "timestamp": 1_700_000_000,
                        "message": {"mid": "mid.1", "text": "hola"},
                    },
                    {
                        "sender": {"id": "user-1"},
                        "message": {"mid": "mid.echo", "text": "eco", "is_echo": True},
                    },
                ],
            }
        ],
    }
    raw_ig = json.dumps(instagram).encode()
    messages = client.parse_webhook(raw_ig, _sign(raw_ig))
    assert len(messages) == 1
    assert messages[0].channel == "instagram"
    assert messages[0].sender == "user-1"
    assert messages[0].text == "hola"
    assert messages[0].provider_message_id == "mid.1"

    whatsapp = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "12345"},
                            "messages": [
                                {
                                    "from": "56911111111",
                                    "id": "wamid.1",
                                    "timestamp": "1700000001",
                                    "type": "text",
                                    "text": {"body": "precio"},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }
    raw_wa = json.dumps(whatsapp).encode()
    inbound = client.parse_webhook(raw_wa, _sign(raw_wa))
    assert inbound[0].channel == "whatsapp"
    assert inbound[0].sender == "56911111111"
    assert inbound[0].text == "precio"


def test_firma_meta_invalida_lanza() -> None:
    client = MetaCloud(_settings())
    body = json.dumps({"object": "instagram", "entry": []}).encode()
    with pytest.raises(WebhookSignatureError):
        client.parse_webhook(body, "sha256=" + "ab" * 32)
    with pytest.raises(WebhookSignatureError):
        client.parse_webhook(body, "")


@pytest.mark.parametrize("channel", ["instagram", "linkedin", "whatsapp"])
def test_frio_no_se_envia(channel: str, respx_mock: Any) -> None:
    route = respx_mock.route().respond(200, json={"messages": [{"id": "no"}]})
    client = MetaCloud(_settings())
    result = client.send_cold(channel, "destino", "hola")
    assert result.status == "manual_pending"
    assert result.channel == channel
    assert cold_channel_result(channel).status == "manual_pending"
    assert route.call_count == 0
    linkedin = client.send_reply(
        "destino",
        "hola",
        user_initiated=True,
        within_24h=True,
        channel="linkedin",
    )
    assert linkedin.status == "manual_pending"
    assert route.call_count == 0


def test_send_reply_exige_ventana(respx_mock: Any) -> None:
    route = respx_mock.post(f"{GRAPH}/12345/messages").respond(
        200,
        json={"messages": [{"id": "wamid.9"}]},
    )
    client = MetaCloud(_settings())
    cold = client.send_reply("56911111111", "hola", user_initiated=False, within_24h=True)
    assert cold.status == "manual_pending"
    closed = client.send_reply(
        "56911111111",
        "hola",
        user_initiated=True,
        within_24h=False,
        opted_in=False,
    )
    assert closed.status == "manual_pending"
    assert route.call_count == 0
    sent = client.send_reply("56911111111", "hola", user_initiated=True, within_24h=True)
    assert sent.status == "sent"
    assert sent.provider_message_id == "wamid.9"
    assert route.call_count == 1
    assert route.calls.last.request.headers["Authorization"] == "Bearer wa-test"
    body = json.loads(route.calls.last.request.content.decode())
    assert body["messaging_product"] == "whatsapp"
    assert body["text"]["body"] == "hola"
    assert GRAPH_VERSION in str(route.calls.last.request.url)


def test_send_reply_instagram(respx_mock: Any) -> None:
    route = respx_mock.post(f"{GRAPH}/me/messages").respond(200, json={"message_id": "mid.9"})
    client = MetaCloud(_settings())
    opted = client.send_reply(
        "user-1",
        "dale",
        user_initiated=True,
        opted_in=True,
        channel="instagram",
    )
    assert opted.status == "sent"
    assert opted.provider_message_id == "mid.9"
    assert route.calls.last.request.headers["Authorization"] == "Bearer ig-test"


def test_dry_run_reply_no_llama_respx(respx_mock: Any) -> None:
    route = respx_mock.route().respond(200, json={"messages": [{"id": "no"}]})
    client = MetaCloud(_settings(dry_run=True))
    result = client.send_reply("56911111111", "hola", user_initiated=True, within_24h=True)
    assert result.status == "blocked"
    assert result.reason == "dry_run"
    fake = build_meta(_settings(app_mode="demo", dry_run=True))
    assert isinstance(fake, FakeMeta)
    assert fake.send_cold("whatsapp", "x", "y").status == "manual_pending"
    assert fake.send_reply("x", "y", user_initiated=False).status == "manual_pending"
    assert route.call_count == 0
    assert isinstance(build_meta(_settings()), MetaCloud)
    assert isinstance(build_meta(_settings(meta_app_secret="")), FakeMeta)
