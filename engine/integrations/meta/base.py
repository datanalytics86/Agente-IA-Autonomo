"""Meta: Instagram y WhatsApp solo responden. El frío queda en manual_pending."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from core.config import Settings
from integrations.errors import WebhookSignatureError
from integrations.results import SendResult

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
COLD_CHANNELS = frozenset({"instagram", "linkedin", "whatsapp"})


class InboundMessage(BaseModel):
    channel: str
    sender: str
    recipient: str
    text: str
    provider_message_id: str
    timestamp: datetime | None = None


class MetaInbound(Protocol):
    def verify_subscription(self, mode: str, token: str, challenge: str) -> str | None: ...

    def parse_webhook(self, body: bytes, signature: str) -> list[InboundMessage]: ...

    def send_reply(
        self,
        recipient: str,
        text: str,
        *,
        user_initiated: bool,
        within_24h: bool = False,
        opted_in: bool = False,
        channel: str = "whatsapp",
    ) -> SendResult: ...

    def send_cold(self, channel: str, recipient: str, text: str) -> SendResult: ...


def _eq(expected: str, presented: str) -> bool:
    left = expected.encode()
    right = presented.encode()
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def verify_meta_signature(body: bytes, signature: str, secret: str) -> None:
    if not secret or not signature:
        raise WebhookSignatureError("firma meta ausente")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not _eq(expected, signature.strip()):
        raise WebhookSignatureError("firma meta inválida")


def subscription_challenge(expected: str, mode: str, token: str, challenge: str) -> str | None:
    if mode != "subscribe" or not expected or not token or not challenge:
        return None
    if not _eq(token, expected):
        return None
    return challenge


def cold_channel_result(channel: str) -> SendResult:
    """Instagram, LinkedIn y WhatsApp en frío no se envían."""
    normalized = channel.strip().lower()
    if normalized not in COLD_CHANNELS:
        raise ValueError(f"canal no es de frío prohibido: {channel}")
    return SendResult(status="manual_pending", reason="frio_prohibido", channel=normalized)


def _epoch(value: object) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        seconds = int(str(value))
    except ValueError:
        return None
    if seconds > 10_000_000_000:
        seconds //= 1000
    return datetime.fromtimestamp(seconds, UTC)


def _loads(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("webhook meta no es JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("webhook meta no es un objeto")
    return payload


def _instagram_entry(entry: Mapping[str, Any]) -> list[InboundMessage]:
    page = str(entry.get("id") or "")
    found: list[InboundMessage] = []
    messaging = entry.get("messaging")
    if not isinstance(messaging, list):
        return found
    for item in messaging:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not isinstance(message, dict) or message.get("is_echo"):
            continue
        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        sender = item.get("sender")
        sender_id = str(sender.get("id")) if isinstance(sender, dict) and sender.get("id") else ""
        if not sender_id:
            continue
        found.append(
            InboundMessage(
                channel="instagram",
                sender=sender_id,
                recipient=page,
                text=text,
                provider_message_id=str(message.get("mid") or ""),
                timestamp=_epoch(item.get("timestamp")),
            )
        )
    return found


def _whatsapp_entry(entry: Mapping[str, Any]) -> list[InboundMessage]:
    found: list[InboundMessage] = []
    changes = entry.get("changes")
    if not isinstance(changes, list):
        return found
    for change in changes:
        if not isinstance(change, dict):
            continue
        value = change.get("value")
        if not isinstance(value, dict):
            continue
        metadata = value.get("metadata")
        phone_id = ""
        if isinstance(metadata, dict):
            phone_id = str(metadata.get("phone_number_id") or "")
        messages = value.get("messages")
        if not isinstance(messages, list):
            continue
        for item in messages:
            if not isinstance(item, dict) or item.get("type") not in {None, "text"}:
                continue
            text_block = item.get("text")
            text = text_block.get("body") if isinstance(text_block, dict) else None
            if not isinstance(text, str) or not text.strip():
                continue
            sender = str(item.get("from") or "")
            if not sender:
                continue
            found.append(
                InboundMessage(
                    channel="whatsapp",
                    sender=sender,
                    recipient=phone_id,
                    text=text,
                    provider_message_id=str(item.get("id") or ""),
                    timestamp=_epoch(item.get("timestamp")),
                )
            )
    return found


def parse_inbound(body: bytes) -> list[InboundMessage]:
    payload = _loads(body)
    object_name = str(payload.get("object") or "")
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return []
    found: list[InboundMessage] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if object_name == "instagram":
            found.extend(_instagram_entry(entry))
        elif object_name == "whatsapp_business_account":
            found.extend(_whatsapp_entry(entry))
    return found


def _reply_block(settings: Settings, channel: str) -> str | None:
    if settings.dry_run:
        return "dry_run"
    if settings.app_mode != "prod":
        return "app_mode"
    if channel == "whatsapp":
        if not settings.whatsapp_token.strip() or not settings.whatsapp_phone_number_id.strip():
            return "credential"
        return None
    if channel == "instagram":
        if not settings.ig_access_token.strip():
            return "credential"
        return None
    return "credential"


class MetaCloud:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify_subscription(self, mode: str, token: str, challenge: str) -> str | None:
        return subscription_challenge(self.settings.meta_verify_token, mode, token, challenge)

    def parse_webhook(self, body: bytes, signature: str) -> list[InboundMessage]:
        verify_meta_signature(body, signature, self.settings.meta_app_secret)
        return parse_inbound(body)

    def send_reply(
        self,
        recipient: str,
        text: str,
        *,
        user_initiated: bool,
        within_24h: bool = False,
        opted_in: bool = False,
        channel: str = "whatsapp",
    ) -> SendResult:
        selected = channel.strip().lower()
        if selected in {"linkedin"} or selected not in {"whatsapp", "instagram"}:
            return cold_channel_result(selected if selected in COLD_CHANNELS else "whatsapp")
        if not user_initiated or not (within_24h or opted_in):
            return SendResult(status="manual_pending", reason="sin_ventana", channel=selected)
        if not recipient.strip() or not text.strip():
            return SendResult(status="failed", reason="vacio", channel=selected)
        reason = _reply_block(self.settings, selected)
        if reason:
            return SendResult(status="blocked", reason=reason, channel=selected)
        if selected == "whatsapp":
            url = f"{GRAPH}/{self.settings.whatsapp_phone_number_id}/messages"
            token = self.settings.whatsapp_token
            payload: dict[str, object] = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient,
                "type": "text",
                "text": {"preview_url": False, "body": text},
            }
        else:
            url = f"{GRAPH}/me/messages"
            token = self.settings.ig_access_token
            payload = {"recipient": {"id": recipient}, "message": {"text": text}}
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=20.0,
            trust_env=False,
        )
        if response.status_code not in {200, 201}:
            return SendResult(
                status="failed",
                reason=f"meta_{response.status_code}",
                channel=selected,
            )
        body = response.json()
        provider_id = ""
        messages = body.get("messages")
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            provider_id = str(messages[0].get("id") or "")
        if not provider_id:
            provider_id = str(body.get("message_id") or "")
        return SendResult(status="sent", provider_message_id=provider_id, channel=selected)

    def send_cold(self, channel: str, recipient: str, text: str) -> SendResult:
        del recipient, text
        return cold_channel_result(channel)


class FakeMeta:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.replies: list[dict[str, str]] = []

    def verify_subscription(self, mode: str, token: str, challenge: str) -> str | None:
        return subscription_challenge(self.settings.meta_verify_token, mode, token, challenge)

    def parse_webhook(self, body: bytes, signature: str) -> list[InboundMessage]:
        del signature
        return parse_inbound(body)

    def send_reply(
        self,
        recipient: str,
        text: str,
        *,
        user_initiated: bool,
        within_24h: bool = False,
        opted_in: bool = False,
        channel: str = "whatsapp",
    ) -> SendResult:
        selected = channel.strip().lower()
        if selected not in {"whatsapp", "instagram"}:
            return cold_channel_result("whatsapp" if selected not in COLD_CHANNELS else selected)
        if not user_initiated or not (within_24h or opted_in):
            return SendResult(status="manual_pending", reason="sin_ventana", channel=selected)
        self.replies.append({"channel": selected, "recipient": recipient, "text": text})
        return SendResult(
            status="sent",
            provider_message_id=f"fake-meta-{len(self.replies)}",
            channel=selected,
        )

    def send_cold(self, channel: str, recipient: str, text: str) -> SendResult:
        del recipient, text
        return cold_channel_result(channel)


def _meta_credential(settings: Settings) -> bool:
    return bool(settings.meta_app_secret.strip() and settings.meta_verify_token.strip())


def build_meta(settings: Settings) -> MetaInbound:
    if settings.app_mode == "demo" or settings.dry_run or not _meta_credential(settings):
        return FakeMeta(settings)
    return MetaCloud(settings)
