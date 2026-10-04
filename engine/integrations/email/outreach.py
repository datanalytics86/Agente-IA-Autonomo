"""Outreach por SMTP del buzón dedicado. No usa el proveedor transaccional."""

from __future__ import annotations

import random
import re
import smtplib
from collections.abc import Callable
from email.message import EmailMessage
from html import escape
from typing import Protocol
from urllib.parse import quote

from core.config import Settings
from integrations.email.base import outreach_block_reason, outreach_has_credential
from integrations.results import SendResult

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_CHANNEL = "email_outreach"


class SmtpTransport(Protocol):
    def send(self, message: EmailMessage) -> str: ...


class StdlibSmtpTransport:
    """Abre el socket recién en `send`. El candado tiene que haber pasado antes."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: EmailMessage) -> str:
        settings = self._settings
        with smtplib.SMTP(
            settings.outreach_smtp_host,
            settings.outreach_smtp_port,
            timeout=30,
        ) as client:
            client.ehlo()
            client.starttls()
            client.ehlo()
            client.login(settings.outreach_smtp_user, settings.outreach_smtp_password)
            client.send_message(message)
        return str(message["Message-ID"] or "")


def outreach_html(html: str, text: str) -> str:
    """Quita imágenes: el outreach no lleva píxel de apertura."""
    cleaned = _IMG_RE.sub("", html or "")
    if cleaned.strip():
        return cleaned
    return f"<p>{escape(text)}</p>"


def build_outreach_message(
    settings: Settings,
    message_id: str,
    to: str,
    subject: str,
    text: str,
    html: str,
) -> EmailMessage:
    base = settings.public_base_url.rstrip("/")
    unsubscribe = f"{base}/baja?mid={quote(message_id, safe='')}"
    message = EmailMessage()
    message["From"] = settings.outreach_from
    message["To"] = to
    message["Subject"] = subject
    message["Reply-To"] = settings.outreach_imap_user
    message["List-Unsubscribe"] = f"<{unsubscribe}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    token = message_id if "@" in message_id else f"{message_id}@outreach.local"
    message["Message-ID"] = f"<{token}>"
    message.set_content(text)
    message.add_alternative(outreach_html(html, text), subtype="html")
    return message


class SmtpOutreach:
    def __init__(
        self,
        settings: Settings,
        *,
        kill_switch: bool = False,
        suppressed: Callable[[str], bool] | None = None,
        transport: SmtpTransport | None = None,
    ) -> None:
        self.settings = settings
        self.kill_switch = kill_switch
        self._suppressed = suppressed or (lambda _to: False)
        self._transport = transport or StdlibSmtpTransport(settings)

    def send(self, message_id: str, to: str, subject: str, text: str, html: str) -> SendResult:
        reason = outreach_block_reason(
            self.settings,
            kill_switch=self.kill_switch,
            credential=outreach_has_credential(self.settings),
        )
        if reason:
            return SendResult(status="blocked", reason=reason, channel=_CHANNEL)
        if self._suppressed(to):
            return SendResult(status="blocked", reason="suppressed", channel=_CHANNEL)
        message = build_outreach_message(self.settings, message_id, to, subject, text, html)
        provider_id = self._transport.send(message)
        return SendResult(
            status="sent",
            provider_message_id=provider_id or str(message["Message-ID"]),
            channel=_CHANNEL,
        )


class FakeOutreach:
    """Guarda el MIME en memoria. El 3 % de rebotes solo corre si hay RNG de simulación."""

    def __init__(
        self,
        settings: Settings,
        *,
        kill_switch: bool = False,
        suppressed: Callable[[str], bool] | None = None,
        rng: random.Random | None = None,
        bounce_rate: float | None = None,
    ) -> None:
        self.settings = settings
        self.kill_switch = kill_switch
        self._suppressed = suppressed or (lambda _to: False)
        self._rng = rng
        if rng is not None and bounce_rate is None:
            self._bounce_rate = 0.03
        else:
            self._bounce_rate = 0.0 if bounce_rate is None else bounce_rate
        self.outbox: list[EmailMessage] = []

    def send(self, message_id: str, to: str, subject: str, text: str, html: str) -> SendResult:
        reason = outreach_block_reason(
            self.settings,
            kill_switch=self.kill_switch,
            credential=outreach_has_credential(self.settings),
        )
        if reason:
            return SendResult(status="blocked", reason=reason, channel=_CHANNEL)
        if self._suppressed(to):
            return SendResult(status="blocked", reason="suppressed", channel=_CHANNEL)
        if (
            self._rng is not None
            and self._bounce_rate > 0
            and self._rng.random() < self._bounce_rate
        ):
            return SendResult(status="bounced", reason="simulado", channel=_CHANNEL)
        message = build_outreach_message(self.settings, message_id, to, subject, text, html)
        self.outbox.append(message)
        return SendResult(
            status="sent",
            provider_message_id=str(message["Message-ID"]),
            channel=_CHANNEL,
        )
