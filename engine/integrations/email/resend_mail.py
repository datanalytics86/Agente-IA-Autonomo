"""Correo transaccional vía Resend. No se usa para outreach en frío."""

from __future__ import annotations

import httpx

from core.config import Settings
from integrations.email.base import is_system_mail, transactional_block_reason
from integrations.results import SendResult

RESEND_URL = "https://api.resend.com/emails"
_CHANNEL = "email_tx"
_INTERNAL_HEADERS = frozenset({"x-mail-kind", "x-consent"})


def _public_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in _INTERNAL_HEADERS}


class ResendTransactional:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(
        self,
        to: str,
        subject: str,
        text: str,
        html: str,
        headers: dict[str, str],
        *,
        consent: bool = False,
        kind: str = "",
    ) -> SendResult:
        if not consent and not is_system_mail(headers, kind):
            return SendResult(status="rejected", reason="sin_consentimiento", channel=_CHANNEL)
        reason = transactional_block_reason(self.settings)
        if reason:
            return SendResult(status="blocked", reason=reason, channel=_CHANNEL)
        payload: dict[str, object] = {
            "from": self.settings.email_tx_from,
            "to": [to],
            "subject": subject,
            "text": text,
            "html": html,
        }
        public = _public_headers(headers)
        if public:
            payload["headers"] = public
        response = httpx.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {self.settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20.0,
            trust_env=False,
        )
        if response.status_code not in {200, 201}:
            return SendResult(
                status="failed",
                reason=f"resend_{response.status_code}",
                channel=_CHANNEL,
            )
        body = response.json()
        message_id = str(body.get("id") or "")
        return SendResult(status="sent", provider_message_id=message_id, channel=_CHANNEL)


class FakeTransactional:
    """Registra el transaccional en memoria. Rechaza igual si no hay consentimiento."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.outbox: list[dict[str, object]] = []

    def send(
        self,
        to: str,
        subject: str,
        text: str,
        html: str,
        headers: dict[str, str],
        *,
        consent: bool = False,
        kind: str = "",
    ) -> SendResult:
        if not consent and not is_system_mail(headers, kind):
            return SendResult(status="rejected", reason="sin_consentimiento", channel=_CHANNEL)
        self.outbox.append(
            {
                "to": to,
                "subject": subject,
                "text": text,
                "html": html,
                "headers": _public_headers(headers),
                "kind": kind,
            }
        )
        return SendResult(
            status="sent",
            provider_message_id=f"fake-tx-{len(self.outbox)}",
            channel=_CHANNEL,
        )
