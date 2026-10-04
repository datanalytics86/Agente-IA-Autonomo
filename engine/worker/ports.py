"""Puertos del worker. Las implementaciones reales o fake se inyectan."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from core.compliance import CheckResult
from worker.clock import Clock


@dataclass(frozen=True)
class PlaceHit:
    place_id: str
    name: str
    formatted_address: str
    commune: str
    city: str
    category: str
    website_uri: str | None
    rating: float | None
    user_rating_count: int | None
    business_status: str
    email: str | None
    instagram_handle: str | None
    linkedin_url: str | None
    phone_public: str | None
    estimated_value_clp: int
    opportunity_score: int
    scenario: str
    unsafe_text: str = ""


@dataclass(frozen=True)
class SendResult:
    status: str
    provider_message_id: str | None = None


@dataclass(frozen=True)
class InboundMail:
    from_email: str
    body: str
    intent: str


@dataclass(frozen=True)
class Preference:
    order_id: str
    url: str
    preference_id: str


@dataclass(frozen=True)
class PaymentFact:
    order_id: str
    provider_payment_id: str
    status: str
    amount_clp: int


@dataclass(frozen=True)
class BookingEvent:
    lead_id: str
    start: datetime
    provider_event_id: str


class LeadSource(Protocol):
    def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]: ...


class OutreachEmail(Protocol):
    def send(
        self,
        message_id: str,
        to: str,
        subject: str,
        text: str,
        html: str,
    ) -> SendResult: ...


class InboundPoller(Protocol):
    def poll(self) -> list[InboundMail]: ...


class Judge(Protocol):
    def review(self, message: dict[str, object], lead: dict[str, object]) -> CheckResult: ...


class BookingPort(Protocol):
    def link_for(self, lead_id: str) -> str: ...

    def poll(self) -> list[BookingEvent]: ...


class PaymentPort(Protocol):
    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference: ...

    def poll(self) -> list[PaymentFact]: ...


class Notifier(Protocol):
    def send_digest(self, text: str) -> None: ...


@dataclass
class Ports:
    places: LeadSource
    outreach: OutreachEmail
    inbound: InboundPoller
    judge: Judge
    bookings: BookingPort
    payments: PaymentPort
    notifier: Notifier
    network_calls: int = 0


@dataclass
class JobContext:
    session: Session
    clock: Clock
    rng: random.Random
    ports: Ports
    allow_send: bool = True
    notes: list[str] = field(default_factory=list)
