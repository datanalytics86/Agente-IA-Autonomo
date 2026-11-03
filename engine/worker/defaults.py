"""Adaptadores por defecto. No abren sockets."""

from __future__ import annotations

import importlib

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
        *,
        lead_id: str = "",
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


def place_from_source(hit: object, *, commune: str, category: str) -> PlaceHit | None:
    """Copia solo campos que ya vienen. Sin email, puntaje o valor no hay lead."""
    email = getattr(hit, "email", None)
    if not isinstance(email, str) or "@" not in email:
        return None
    score = getattr(hit, "opportunity_score", None)
    value = getattr(hit, "estimated_value_clp", None)
    if isinstance(score, bool) or not isinstance(score, int):
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    raw_commune = getattr(hit, "commune", None)
    if isinstance(raw_commune, str) and raw_commune.strip():
        commune_value = raw_commune.strip()
    elif commune.strip():
        commune_value = commune.strip()
    else:
        return None
    name = getattr(hit, "name", None)
    place_id = getattr(hit, "place_id", None)
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(place_id, str) or not place_id.strip():
        return None
    raw_category = getattr(hit, "category", None)
    category_value = raw_category.strip() if isinstance(raw_category, str) else ""
    if not category_value:
        category_value = category.strip()
    if not category_value:
        return None
    status = getattr(hit, "business_status", None)
    if not isinstance(status, str) or not status.strip():
        return None
    city = getattr(hit, "city", None)
    address = getattr(hit, "formatted_address", None)
    rating = getattr(hit, "rating", None)
    reviews = getattr(hit, "user_rating_count", None)
    website = getattr(hit, "website_uri", None)
    phone = getattr(hit, "phone_public", None)
    if not isinstance(phone, str):
        phone = getattr(hit, "national_phone_number", None)
    instagram = getattr(hit, "instagram_handle", None)
    linkedin = getattr(hit, "linkedin_url", None)
    scenario = getattr(hit, "scenario", None)
    unsafe = getattr(hit, "unsafe_text", None)
    return PlaceHit(
        place_id=place_id.strip(),
        name=name.strip(),
        formatted_address=address if isinstance(address, str) else "",
        commune=commune_value,
        city=city.strip() if isinstance(city, str) else "",
        category=category_value,
        website_uri=website if isinstance(website, str) else None,
        rating=float(rating)
        if isinstance(rating, int | float) and not isinstance(rating, bool)
        else None,
        user_rating_count=reviews
        if isinstance(reviews, int) and not isinstance(reviews, bool)
        else None,
        business_status=status.strip(),
        email=email.strip(),
        instagram_handle=instagram if isinstance(instagram, str) else None,
        linkedin_url=linkedin if isinstance(linkedin, str) else None,
        phone_public=phone if isinstance(phone, str) else None,
        estimated_value_clp=value,
        opportunity_score=score,
        scenario=scenario if isinstance(scenario, str) else "",
        unsafe_text=unsafe if isinstance(unsafe, str) else "",
    )


class _PlacesBridge:
    def __init__(self, source: object) -> None:
        self._source = source

    def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]:
        raw = self._source.search(commune, category_slug, limit)  # type: ignore[attr-defined]
        found: list[PlaceHit] = []
        for hit in raw:
            mapped = place_from_source(hit, commune=commune, category=category_slug)
            if mapped is not None:
                found.append(mapped)
        return found


class _SmtpBridge:
    def send(
        self,
        message_id: str,
        to: str,
        subject: str,
        text: str,
        html: str,
    ) -> SendResult:
        email_mod = importlib.import_module("integrations.email")
        result = email_mod.build_outreach_email(get_settings(), kill_switch=True).send(
            message_id, to, subject, text, html
        )
        return SendResult(status=result.status, provider_message_id=result.provider_message_id)


class _InboundBridge:
    def __init__(self, poller: object) -> None:
        self._poller = poller

    def poll(self) -> list[InboundMail]:
        from core.compliance import is_opt_out, looks_like_injection

        found: list[InboundMail] = []
        for mail in self._poller.poll():  # type: ignore[attr-defined]
            body = getattr(mail, "text", None)
            if not isinstance(body, str):
                body = getattr(mail, "body", "")
            if not isinstance(body, str) or not body.strip():
                continue
            raw_from = getattr(mail, "from_addr", None) or getattr(mail, "from_email", "")
            if not isinstance(raw_from, str):
                continue
            email = raw_from
            if "<" in raw_from and ">" in raw_from:
                email = raw_from.split("<", 1)[1].split(">", 1)[0].strip()
            if "@" not in email:
                continue
            if is_opt_out(body):
                intent = "opt_out"
            elif looks_like_injection(body):
                intent = "prompt_injection"
            else:
                continue
            found.append(InboundMail(from_email=email.strip(), body=body, intent=intent))
        return found


class _BookingBridge:
    def __init__(self, inner: object) -> None:
        self._inner = inner

    def link_for(self, lead_id: str) -> str:
        link = self._inner.link_for(lead_id)  # type: ignore[attr-defined]
        return link if isinstance(link, str) else ""

    def poll(self) -> list[BookingEvent]:
        return []


class _PaymentBridge:
    def __init__(self, inner: object) -> None:
        self._inner = inner

    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference:
        pref = self._inner.create_preference(order_id, title, amount_clp)  # type: ignore[attr-defined]
        url = getattr(pref, "url", None) or getattr(pref, "checkout_url", None)
        preference_id = getattr(pref, "preference_id", None)
        if (
            not isinstance(url, str)
            or not url
            or not isinstance(preference_id, str)
            or not preference_id
        ):
            return Preference(order_id=order_id, url="", preference_id="")
        return Preference(order_id=order_id, url=url, preference_id=preference_id)

    def poll(self) -> list[PaymentFact]:
        return []


def _armed(credential: bool) -> bool:
    settings = get_settings()
    return settings.app_mode == "prod" and settings.dry_run is False and credential


def build_default_ports() -> Ports:
    """Un solo armado. Demo y dry-run quedan en stubs. Prod con credencial usa el adaptador real."""
    settings = get_settings()
    places: object = EmptySource()
    if _armed(bool(settings.google_places_api_key.strip())):
        places_mod = importlib.import_module("integrations.places")
        places = _PlacesBridge(places_mod.build_places(settings))
    outreach: object = GuardedOutreach()
    smtp = bool(
        settings.outreach_smtp_host.strip()
        and settings.outreach_smtp_user.strip()
        and settings.outreach_smtp_password
        and settings.outreach_enabled
    )
    if _armed(smtp):
        outreach = _SmtpBridge()
    inbound: object = EmptyInbound()
    imap = bool(
        settings.outreach_imap_host.strip()
        and settings.outreach_imap_user.strip()
        and settings.outreach_imap_password
    )
    if _armed(imap):
        email_mod = importlib.import_module("integrations.email")
        inbound = _InboundBridge(email_mod.build_inbound_poller(settings))
    bookings: object = LocalBooking()
    booking_ready = bool(
        settings.booking_link.strip()
        or settings.calcom_webhook_secret.strip()
        or settings.calendly_webhook_signing_key.strip()
    )
    if _armed(booking_ready):
        booking_mod = importlib.import_module("integrations.booking")
        bookings = _BookingBridge(booking_mod.build_booking(settings))
    payments: object = LocalPayments()
    if _armed(bool(settings.mp_access_token.strip())):
        payments_mod = importlib.import_module("integrations.payments")
        payments = _PaymentBridge(payments_mod.build_payments(settings))
    return Ports(
        places=places,  # type: ignore[arg-type]
        outreach=outreach,  # type: ignore[arg-type]
        inbound=inbound,  # type: ignore[arg-type]
        judge=RulesJudge(),
        bookings=bookings,  # type: ignore[arg-type]
        payments=payments,  # type: ignore[arg-type]
        notifier=LogNotifier(),
    )
