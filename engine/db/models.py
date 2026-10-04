"""Modelos SQLAlchemy 2 del contrato de base de datos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """DateTime consciente de UTC, también cuando SQLite devuelve valores naive."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError("se esperaba datetime")
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        parsed = value
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
        if not isinstance(parsed, datetime):
            raise TypeError("se esperaba datetime")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint(
            "opportunity_score >= 0 AND opportunity_score <= 100",
            name="opportunity_score_range",
        ),
        Index("ix_leads_commune_business", "commune", "business"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(32))
    business: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64))
    city: Mapped[str] = mapped_column(String(120))
    commune: Mapped[str] = mapped_column(String(120))
    address_public: Mapped[str | None] = mapped_column(Text)
    place_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    google_maps_uri: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    website_audit: Mapped[Any | None] = mapped_column(JSON)
    opportunity_score: Mapped[int] = mapped_column(Integer)
    rating: Mapped[float | None] = mapped_column(Float)
    reviews: Mapped[int | None] = mapped_column(Integer)
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_email_source_url: Mapped[str | None] = mapped_column(Text)
    instagram_handle: Mapped[str | None] = mapped_column(String(120))
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    phone_public: Mapped[str | None] = mapped_column(String(32))
    consent: Mapped[Any | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), index=True)
    paused_from: Mapped[str | None] = mapped_column(String(32))
    hitl_reason: Mapped[str | None] = mapped_column(Text)
    close_reason: Mapped[str | None] = mapped_column(Text)
    estimated_value_clp: Mapped[int] = mapped_column(Integer)
    high_value: Mapped[bool] = mapped_column(Boolean, default=False)
    tone: Mapped[str] = mapped_column(String(8))
    diagnosis: Mapped[Any | None] = mapped_column(JSON)
    next_action_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)
    anonymized_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class LeadEvent(Base):
    __tablename__ = "lead_events"
    __table_args__ = (Index("ix_lead_events_lead_id_ts", "lead_id", "ts"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    from_status: Mapped[str] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_channel_status_scheduled_at", "channel", "status", "scheduled_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    thread_id: Mapped[str] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(8))
    channel: Mapped[str] = mapped_column(String(32))
    sequence_step: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str | None] = mapped_column(Text)
    check_result: Mapped[Any | None] = mapped_column(JSON)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    intent: Mapped[str | None] = mapped_column(String(64))
    intent_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[Any] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(320))
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    path: Mapped[str] = mapped_column(Text)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, default=new_id)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    meta: Mapped[Any | None] = mapped_column(JSON)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    package_code: Mapped[str] = mapped_column(String(32))
    amount_clp: Mapped[int] = mapped_column(Integer)
    iva_clp: Mapped[int] = mapped_column(Integer)
    total_clp: Mapped[int] = mapped_column(Integer)
    deposit_percent: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    checkout_url: Mapped[str | None] = mapped_column(Text)
    provider_preference_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    provider: Mapped[str] = mapped_column(String(32))
    provider_payment_id: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(32))
    amount_clp: Mapped[int] = mapped_column(Integer)
    raw: Mapped[Any | None] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    status: Mapped[str] = mapped_column(String(32))
    intake: Mapped[Any | None] = mapped_column(JSON)
    revisions_used: Mapped[int] = mapped_column(Integer, default=0)
    max_revisions: Mapped[int] = mapped_column(Integer)
    domain: Mapped[str | None] = mapped_column(String(255))
    deploy_url: Mapped[str | None] = mapped_column(Text)
    portal_token: Mapped[str] = mapped_column(String(64), unique=True, default=new_id)
    delivered_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class Suppression(Base):
    __tablename__ = "suppression"
    __table_args__ = (
        UniqueConstraint("kind", "value_hash", name="uq_suppression_kind_value_hash"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16))
    value_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class DataRequest(Base):
    __tablename__ = "data_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16))
    requester_email: Mapped[str] = mapped_column(String(320))
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    due_at: Mapped[datetime] = mapped_column(UtcDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    agent: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    prompt_name: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    tokens_in: Mapped[int] = mapped_column(Integer)
    tokens_out: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"))
    ts: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, index=True)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    job: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String(16))
    processed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    ts: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, index=True)
    agent: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(8))
    message: Mapped[str] = mapped_column(Text)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"))
    meta: Mapped[Any | None] = mapped_column(JSON)


class Setting(Base):
    __tablename__ = "settings_kv"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_by: Mapped[str] = mapped_column(String(320))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32))
    event_id: Mapped[str] = mapped_column(String(255))
    received_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class WorkerLock(Base):
    __tablename__ = "worker_lock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(String(120))
    heartbeat_at: Mapped[datetime] = mapped_column(UtcDateTime)
