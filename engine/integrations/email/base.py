"""Protocolos de correo y fábricas. El candado de outreach vive en el envío."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import Settings
from integrations.results import SendResult

SYSTEM_KINDS = frozenset({"recibo", "portal", "derechos"})


class InboundMail(BaseModel):
    message_id: str
    from_addr: str
    to_addr: str
    subject: str
    text: str
    in_reply_to: str | None = None
    intent: str = ""

    @property
    def from_email(self) -> str:
        return bare_address(self.from_addr)

    @property
    def body(self) -> str:
        return self.text


def bare_address(value: str) -> str:
    text = value.strip()
    start = text.rfind("<")
    end = text.rfind(">")
    if start != -1 and end > start:
        text = text[start + 1 : end]
    return text.strip().lower()


class TransactionalEmail(Protocol):
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
    ) -> SendResult: ...


class OutreachEmail(Protocol):
    def send(self, message_id: str, to: str, subject: str, text: str, html: str) -> SendResult: ...


class InboundPoller(Protocol):
    def poll(self) -> list[InboundMail]: ...


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "si", "sí"}
    return bool(value)


def outreach_has_credential(settings: Settings) -> bool:
    """SMTP, buzón IMAP (Reply-To) y URL pública para la baja de un clic."""
    return bool(
        settings.outreach_smtp_host.strip()
        and settings.outreach_smtp_user.strip()
        and settings.outreach_smtp_password
        and settings.outreach_imap_user.strip()
        and settings.outreach_from.strip()
        and settings.public_base_url.strip()
    )


def outreach_block_reason(
    settings: Settings,
    *,
    kill_switch: bool,
    credential: bool,
) -> str | None:
    """None solo si DRY_RUN está apagado y el cuádruple candado está cerrado a favor del envío.

    El cuádruple es APP_MODE=prod, OUTREACH_ENABLED, kill_switch armado y credencial.
    DRY_RUN es un candado extra: con true no hay socket aunque los otros cuatro pasen.
    """
    if settings.dry_run:
        return "dry_run"
    if settings.app_mode != "prod":
        return "app_mode"
    if not settings.outreach_enabled:
        return "outreach_disabled"
    if not kill_switch:
        return "kill_switch"
    if not credential:
        return "credential"
    return None


def transactional_block_reason(settings: Settings) -> str | None:
    if settings.dry_run:
        return "dry_run"
    if settings.app_mode != "prod":
        return "app_mode"
    if not settings.resend_api_key.strip() or not settings.email_tx_from.strip():
        return "credential"
    return None


def is_system_mail(headers: Mapping[str, str], kind: str) -> bool:
    raw = kind.strip().lower()
    if not raw:
        for key, value in headers.items():
            if key.lower() == "x-mail-kind":
                raw = str(value).strip().lower()
                break
    return raw in SYSTEM_KINDS


def resolve_kill_switch(session: Session | None, explicit: bool | None) -> bool:
    """Sin sesión ni valor explícito el interruptor sigue detenido (default false)."""
    if explicit is not None:
        return explicit
    if session is None:
        return False
    from db.repositories import SettingsRepository

    return _as_bool(SettingsRepository(session).get("kill_switch", False))


def resolve_suppression(
    session: Session | None,
    explicit: Callable[[str], bool] | None,
) -> Callable[[str], bool]:
    if explicit is not None:
        return explicit
    if session is None:
        return lambda _email: False
    from db.repositories import SuppressionRepository

    repo = SuppressionRepository(session)

    def suppressed(email: str) -> bool:
        if repo.contains("email", email):
            return True
        if "@" not in email:
            return False
        return repo.contains("domain", email.rsplit("@", 1)[-1])

    return suppressed


def _use_fake(settings: Settings, *, credential: bool) -> bool:
    return settings.app_mode == "demo" or settings.dry_run or not credential


def build_transactional_email(settings: Settings) -> TransactionalEmail:
    from integrations.email.resend_mail import FakeTransactional, ResendTransactional

    credential = bool(settings.resend_api_key.strip() and settings.email_tx_from.strip())
    if _use_fake(settings, credential=credential):
        return FakeTransactional(settings)
    return ResendTransactional(settings)


def build_outreach_email(
    settings: Settings,
    *,
    kill_switch: bool | None = None,
    session: Session | None = None,
    suppressed: Callable[[str], bool] | None = None,
    transport: object | None = None,
) -> OutreachEmail:
    from integrations.email.outreach import FakeOutreach, SmtpOutreach

    armed = resolve_kill_switch(session, kill_switch)
    check = resolve_suppression(session, suppressed)
    if _use_fake(settings, credential=outreach_has_credential(settings)):
        return FakeOutreach(settings, kill_switch=armed, suppressed=check)
    return SmtpOutreach(
        settings,
        kill_switch=armed,
        suppressed=check,
        transport=transport,  # type: ignore[arg-type]
    )


def build_inbound_poller(
    settings: Settings,
    *,
    client_factory: object | None = None,
) -> InboundPoller:
    from integrations.email.inbound import FakeInbound, ImapPoller

    credential = bool(
        settings.outreach_imap_host.strip()
        and settings.outreach_imap_user.strip()
        and settings.outreach_imap_password
    )
    if _use_fake(settings, credential=credential):
        return FakeInbound()
    if client_factory is None:
        return ImapPoller(settings)
    return ImapPoller(settings, client_factory=client_factory)  # type: ignore[arg-type]
