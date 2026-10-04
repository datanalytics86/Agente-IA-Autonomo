"""Fábrica única de puertos. En prod elige el adaptador real o uno Disabled."""

from __future__ import annotations

import importlib
import logging
from contextvars import ContextVar, Token
from datetime import datetime, time
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import Settings, get_settings
from db.models import Event
from db.repositories import EventRepository
from worker.ports import (
    BookingEvent,
    BookingPort,
    InboundMail,
    InboundPoller,
    LeadSource,
    Notifier,
    OutreachEmail,
    PaymentFact,
    PaymentPort,
    PlaceHit,
    Ports,
    Preference,
    SendResult,
)
from worker.testing_ports import RulesJudge, build_default_ports

logger = logging.getLogger("worker.wiring")


def _adapter(module: str, name: str) -> Any:
    # importlib: mypy no sigue integrations (excluido del proyecto).
    return getattr(importlib.import_module(module), name)


CHANNEL_NAMES = (
    "places",
    "auditor",
    "outreach",
    "inbound",
    "booking",
    "payments",
    "hosting",
    "meta",
    "notifier",
    "email_tx",
)

_bound: ContextVar[Session | None] = ContextVar("worker_wiring_session", default=None)
_noted: set[tuple[str, str]] = set()


def bind_worker_session(session: Session) -> Token[Session | None]:
    return _bound.set(session)


def unbind_worker_session(token: Token[Session | None]) -> None:
    _bound.reset(token)


def clear_disabled_notes() -> None:
    _noted.clear()


def _local_now() -> datetime:
    tz = ZoneInfo(get_settings().tz or "America/Santiago")
    return datetime.now(tz)


def _warned_today(session: Session, channel: str, start: datetime) -> bool:
    found = session.scalar(
        select(Event.id)
        .where(
            Event.agent == channel,
            Event.level == "warn",
            Event.message.like("canal deshabilitado:%"),
            Event.ts >= start,
        )
        .limit(1)
    )
    return found is not None


def note_disabled(channel: str, missing: str) -> None:
    """Un warn por canal y día. Sin sesión no abre la base ni un socket."""
    now = _local_now()
    key = (channel, now.date().isoformat())
    if key in _noted:
        return
    message = f"canal deshabilitado: falta {missing}"
    session = _bound.get()
    if session is None:
        _noted.add(key)
        logger.warning(message)
        return
    start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    if _warned_today(session, channel, start):
        _noted.add(key)
        return
    EventRepository(session).append(agent=channel, level="warn", message=message)
    _noted.add(key)


def _label(missing: list[str]) -> str:
    if not missing:
        return "real"
    return "deshabilitado: falta " + ", ".join(missing)


def _places_missing(settings: Settings) -> list[str]:
    if not settings.google_places_api_key.strip():
        return ["GOOGLE_PLACES_API_KEY"]
    return []


def _outreach_missing(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.outreach_smtp_host.strip():
        missing.append("OUTREACH_SMTP_HOST")
    if not settings.outreach_smtp_user.strip():
        missing.append("OUTREACH_SMTP_USER")
    if not settings.outreach_smtp_password:
        missing.append("OUTREACH_SMTP_PASSWORD")
    if not settings.outreach_imap_user.strip():
        missing.append("OUTREACH_IMAP_USER")
    if not settings.outreach_from.strip():
        missing.append("OUTREACH_FROM")
    if not settings.public_base_url.strip():
        missing.append("PUBLIC_BASE_URL")
    return missing


def _inbound_missing(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.outreach_imap_host.strip():
        missing.append("OUTREACH_IMAP_HOST")
    if not settings.outreach_imap_user.strip():
        missing.append("OUTREACH_IMAP_USER")
    if not settings.outreach_imap_password:
        missing.append("OUTREACH_IMAP_PASSWORD")
    return missing


def _booking_missing(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.booking_link.strip():
        missing.append("BOOKING_LINK")
    if settings.booking_provider == "calendly":
        if not settings.calendly_webhook_signing_key.strip():
            missing.append("CALENDLY_WEBHOOK_SIGNING_KEY")
    elif not settings.calcom_webhook_secret.strip():
        missing.append("CALCOM_WEBHOOK_SECRET")
    return missing


def _payments_missing(settings: Settings) -> list[str]:
    if not settings.mp_access_token.strip():
        return ["MP_ACCESS_TOKEN"]
    return []


def _hosting_missing(settings: Settings) -> list[str]:
    if settings.hosting_provider != "cloudflare_pages":
        return []
    missing: list[str] = []
    if not settings.cloudflare_api_token.strip():
        missing.append("CLOUDFLARE_API_TOKEN")
    if not settings.cloudflare_account_id.strip():
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    return missing


def _meta_missing(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.meta_app_secret.strip():
        missing.append("META_APP_SECRET")
    if not settings.meta_verify_token.strip():
        missing.append("META_VERIFY_TOKEN")
    return missing


def _email_tx_missing(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.resend_api_key.strip():
        missing.append("RESEND_API_KEY")
    if not settings.email_tx_from.strip():
        missing.append("EMAIL_TX_FROM")
    return missing


def _live_status(settings: Settings) -> dict[str, str]:
    return {
        "places": _label(_places_missing(settings)),
        # PageSpeed es opcional: sin key el auditor HTML igual existe.
        "auditor": "real",
        "outreach": _label(_outreach_missing(settings)),
        "inbound": _label(_inbound_missing(settings)),
        "booking": _label(_booking_missing(settings)),
        "payments": _label(_payments_missing(settings)),
        "hosting": _label(_hosting_missing(settings)),
        "meta": _label(_meta_missing(settings)),
        "notifier": _label(_notifier_missing(settings)),
        "email_tx": _label(_email_tx_missing(settings)),
    }


def channel_status(settings: Settings) -> dict[str, str]:
    """`real`, `dry_run` o `deshabilitado: falta X` por canal."""
    if settings.app_mode != "prod":
        return {name: "dry_run" for name in CHANNEL_NAMES}
    live = _live_status(settings)
    if not settings.dry_run:
        return live
    return {name: "dry_run" if live[name] == "real" else live[name] for name in CHANNEL_NAMES}


class DisabledPlaces:
    def __init__(self, missing: str) -> None:
        self.missing = missing

    def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]:
        del commune, category_slug, limit
        note_disabled("places", self.missing)
        return []


class DisabledOutreach:
    def __init__(self, missing: str) -> None:
        self.missing = missing

    def send(
        self,
        message_id: str,
        to: str,
        subject: str,
        text: str,
        html: str,
    ) -> SendResult:
        del message_id, to, subject, text, html
        note_disabled("outreach", self.missing)
        return SendResult(status="blocked")


class DisabledInbound:
    def __init__(self, missing: str) -> None:
        self.missing = missing

    def poll(self) -> list[InboundMail]:
        note_disabled("inbound", self.missing)
        return []


class DisabledBooking:
    def __init__(self, missing: str) -> None:
        self.missing = missing

    def link_for(self, lead_id: str) -> str:
        del lead_id
        note_disabled("booking", self.missing)
        return ""

    def poll(self) -> list[BookingEvent]:
        note_disabled("booking", self.missing)
        return []


class DisabledPayments:
    def __init__(self, missing: str) -> None:
        self.missing = missing

    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference:
        del title, amount_clp
        note_disabled("payments", self.missing)
        return Preference(order_id=order_id, url="", preference_id="")

    def poll(self) -> list[PaymentFact]:
        note_disabled("payments", self.missing)
        return []


class DisabledNotifier:
    def __init__(self, missing: str) -> None:
        self.missing = missing

    def send_digest(self, text: str) -> None:
        del text
        note_disabled("notifier", self.missing)


class DisabledHosting:
    def __init__(self, missing: str) -> None:
        self.missing = missing

    def publish(self, project_id: str, files: object, domain: str | None) -> str:
        del project_id, files, domain
        note_disabled("hosting", self.missing)
        return ""

    def domain_allowed(self, domain: str) -> bool:
        del domain
        note_disabled("hosting", self.missing)
        return False


class DisabledMeta:
    def __init__(self, missing: str) -> None:
        self.missing = missing

    def verify_subscription(self, mode: str, token: str, challenge: str) -> None:
        del mode, token, challenge
        note_disabled("meta", self.missing)
        return None

    def parse_webhook(self, body: bytes, signature: str) -> list[object]:
        del body, signature
        note_disabled("meta", self.missing)
        return []

    def send_reply(self, recipient: str, text: str, **kwargs: object) -> SendResult:
        del recipient, text, kwargs
        note_disabled("meta", self.missing)
        return SendResult(status="blocked")

    def send_cold(self, channel: str, recipient: str, text: str) -> SendResult:
        del channel, recipient, text
        note_disabled("meta", self.missing)
        return SendResult(status="blocked")


def _notifier_missing(settings: Settings) -> list[str]:
    missing = _adapter("integrations.notify", "notifier_missing")(settings)
    return cast(list[str], missing)


def _places(settings: Settings) -> LeadSource:
    missing = _places_missing(settings)
    if missing:
        return DisabledPlaces(", ".join(missing))
    source = _adapter("integrations.places", "GooglePlacesSource")
    return cast(
        LeadSource,
        source(
            settings.google_places_api_key,
            min_rating=settings.scout_min_rating,
            min_reviews=settings.scout_min_reviews,
            suspend_network=settings.dry_run,
        ),
    )


def _outreach(settings: Settings, session: Session | None) -> OutreachEmail:
    missing = _outreach_missing(settings)
    has_credential = _adapter("integrations.email.base", "outreach_has_credential")
    if missing or not has_credential(settings):
        return DisabledOutreach(", ".join(missing or ["OUTREACH_SMTP_HOST"]))
    resolve_kill_switch = _adapter("integrations.email.base", "resolve_kill_switch")
    resolve_suppression = _adapter("integrations.email.base", "resolve_suppression")
    smtp = _adapter("integrations.email.outreach", "SmtpOutreach")
    return cast(
        OutreachEmail,
        smtp(
            settings,
            kill_switch=resolve_kill_switch(session, None),
            suppressed=resolve_suppression(session, None),
        ),
    )


def _inbound(settings: Settings) -> InboundPoller:
    missing = _inbound_missing(settings)
    if missing:
        return DisabledInbound(", ".join(missing))
    poller = _adapter("integrations.email.inbound", "ImapPoller")
    return cast(InboundPoller, poller(settings))


def _booking(settings: Settings) -> BookingPort:
    missing = _booking_missing(settings)
    if missing:
        return DisabledBooking(", ".join(missing))
    if settings.booking_provider == "calendly":
        booking = _adapter("integrations.booking", "CalendlyBooking")
    else:
        booking = _adapter("integrations.booking", "CalComBooking")
    return cast(BookingPort, booking(settings))


def _payments(settings: Settings) -> PaymentPort:
    missing = _payments_missing(settings)
    if missing:
        return DisabledPayments(", ".join(missing))
    provider = _adapter("integrations.payments", "MercadoPagoProvider")
    return cast(PaymentPort, provider(settings))


def _notifier(settings: Settings) -> Notifier:
    missing = _notifier_missing(settings)
    if missing:
        return DisabledNotifier(", ".join(missing))
    notifier = _adapter("integrations.notify", "OwnerNotifier")
    return cast(Notifier, notifier(settings))


def _auditor(settings: Settings) -> object:
    auditor = _adapter("integrations.pagespeed.base", "HttpWebAuditor")
    base = settings.public_base_url.strip() or "http://localhost"
    return cast(
        object,
        auditor(
            user_agent=f"AgenciaBot/1.0 (+{base})",
            pagespeed_key=settings.pagespeed_api_key,
        ),
    )


def _hosting(settings: Settings, session: Session | None) -> object:
    missing = _hosting_missing(settings)
    if missing:
        return DisabledHosting(", ".join(missing))
    if settings.hosting_provider == "cloudflare_pages":
        pages = _adapter("integrations.hosting.base", "CloudflarePagesHosting")
        return cast(
            object,
            pages(
                account_id=settings.cloudflare_account_id,
                token=settings.cloudflare_api_token,
                session=session,
            ),
        )
    sites = _adapter("integrations.hosting.base", "resolve_sites_dir")
    caddy = _adapter("integrations.hosting.base", "CaddyHosting")
    return cast(object, caddy(sites(settings), session=session))


def _meta(settings: Settings) -> object:
    missing = _meta_missing(settings)
    if missing:
        return DisabledMeta(", ".join(missing))
    meta = _adapter("integrations.meta", "MetaCloud")
    return cast(object, meta(settings))


def build_ports(settings: Settings, session: Session | None = None) -> Ports:
    """Demo (o cualquier modo que no sea prod) usa testing_ports. Prod no."""
    if settings.app_mode != "prod":
        return build_default_ports()
    return Ports(
        places=_places(settings),
        outreach=_outreach(settings, session),
        inbound=_inbound(settings),
        judge=RulesJudge(),
        bookings=_booking(settings),
        payments=_payments(settings),
        notifier=_notifier(settings),
        auditor=_auditor(settings),
        hosting=_hosting(settings, session),
        meta=_meta(settings),
    )
