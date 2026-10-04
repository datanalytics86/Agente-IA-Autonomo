"""Stubs de demo y tests. No abren sockets y no se usan en APP_MODE=prod."""

from __future__ import annotations

from core.compliance import CheckResult, check_rules
from core.config import get_settings
from worker.copywriter import checker_settings
from worker.ports import (
    BookingEvent,
    InboundMail,
    PaymentFact,
    PlaceHit,
    Ports,
    Preference,
    SendResult,
)


class EmptySource:
    def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]:
        return []


class GuardedOutreach:
    """Triple candado de entorno. Sin SMTP en este módulo: nunca abre un socket."""

    def send(
        self,
        message_id: str,
        to: str,
        subject: str,
        text: str,
        html: str,
    ) -> SendResult:
        settings = get_settings()
        credential = bool(settings.outreach_smtp_host and settings.outreach_smtp_user)
        allowed = (
            settings.app_mode == "prod"
            and settings.outreach_enabled
            and settings.dry_run is False
            and credential
        )
        if not allowed:
            return SendResult(status="blocked", provider_message_id=None)
        return SendResult(status="blocked", provider_message_id=f"blocked-{message_id}")


class EmptyInbound:
    def poll(self) -> list[InboundMail]:
        return []


class RulesJudge:
    def review(self, message: dict[str, object], lead: dict[str, object]) -> CheckResult:
        return check_rules(message, lead, checker_settings())


class LocalBooking:
    def link_for(self, lead_id: str) -> str:
        base = get_settings().public_base_url.rstrip("/") or "http://localhost"
        return f"{base}/agendar?lead_id={lead_id}"

    def poll(self) -> list[BookingEvent]:
        return []


class LocalPayments:
    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference:
        base = get_settings().public_base_url.rstrip("/") or "http://localhost"
        return Preference(
            order_id=order_id,
            url=f"{base}/pago/{order_id}",
            preference_id=f"local-{order_id}",
        )

    def poll(self) -> list[PaymentFact]:
        return []


class LogNotifier:
    def send_digest(self, text: str) -> None:
        return None


def build_default_ports() -> Ports:
    return Ports(
        places=EmptySource(),
        outreach=GuardedOutreach(),
        inbound=EmptyInbound(),
        judge=RulesJudge(),
        bookings=LocalBooking(),
        payments=LocalPayments(),
        notifier=LogNotifier(),
    )
