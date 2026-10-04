"""Aviso al dueño: correo transaccional y, si hay token, Telegram. Sin outreach."""

from __future__ import annotations

import logging
from html import escape
from typing import Protocol

from core.config import Settings
from integrations.email.base import TransactionalEmail

logger = logging.getLogger("integrations.notify")

_TELEGRAM = "https://api.telegram.org"


class _Poster(Protocol):
    def __call__(self, url: str, payload: dict[str, object]) -> None: ...


def email_digest_ready(settings: Settings) -> bool:
    return bool(
        settings.notify_email.strip()
        and settings.resend_api_key.strip()
        and settings.email_tx_from.strip()
    )


def telegram_digest_ready(settings: Settings) -> bool:
    return bool(settings.telegram_bot_token.strip() and settings.telegram_chat_id.strip())


def notifier_missing(settings: Settings) -> list[str]:
    """Vacío si al menos un canal del digest puede salir. Si no, qué variable falta."""
    if email_digest_ready(settings) or telegram_digest_ready(settings):
        return []
    missing: list[str] = []
    if not settings.notify_email.strip():
        missing.append("NOTIFY_EMAIL")
    else:
        if not settings.resend_api_key.strip():
            missing.append("RESEND_API_KEY")
        if not settings.email_tx_from.strip():
            missing.append("EMAIL_TX_FROM")
    if not settings.telegram_bot_token.strip():
        missing.append("TELEGRAM_BOT_TOKEN")
    elif not settings.telegram_chat_id.strip():
        missing.append("TELEGRAM_CHAT_ID")
    return missing


def _default_post(url: str, payload: dict[str, object]) -> None:
    import httpx

    httpx.post(url, json=payload, timeout=20.0, trust_env=False)


class OwnerNotifier:
    """Email a NOTIFY_EMAIL y Telegram si hay token. Dry-run no abre sockets."""

    def __init__(
        self,
        settings: Settings,
        *,
        mailer: TransactionalEmail | None = None,
        post: _Poster | None = None,
    ) -> None:
        self.settings = settings
        self._post = post or _default_post
        self._mailer = mailer
        if mailer is None and email_digest_ready(settings):
            from integrations.email.resend_mail import ResendTransactional

            self._mailer = ResendTransactional(settings)

    def send_digest(self, text: str) -> None:
        if self.settings.app_mode != "prod" or self.settings.dry_run:
            return
        self._email(text)
        self._telegram(text)

    def _email(self, text: str) -> None:
        if self._mailer is None or not email_digest_ready(self.settings):
            return
        try:
            self._mailer.send(
                self.settings.notify_email.strip(),
                "Digest de aprobaciones",
                text,
                f"<p>{escape(text)}</p>",
                {},
                consent=True,
            )
        except Exception:
            logger.warning("el digest por email no salió", exc_info=True)

    def _telegram(self, text: str) -> None:
        if not telegram_digest_ready(self.settings):
            return
        token = self.settings.telegram_bot_token.strip()
        payload: dict[str, object] = {
            "chat_id": self.settings.telegram_chat_id.strip(),
            "text": text[:4000],
        }
        try:
            self._post(f"{_TELEGRAM}/bot{token}/sendMessage", payload)
        except Exception:
            logger.warning("el digest por telegram no salió", exc_info=True)
