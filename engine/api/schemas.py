"""Modelos de entrada y salida. Los nombres alimentan el OpenAPI."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ActionName = Literal["scout", "cycle", "followups", "digest"]


def _email(value: str) -> str:
    cleaned = value.strip().lower()
    if _EMAIL.match(cleaned) is None:
        raise ValueError("email inválido")
    return cleaned


def _required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("vacío")
    return cleaned


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorBody(BaseModel):
    error: ErrorDetail


class Accepted(BaseModel):
    id: str
    status: str


class Package(BaseModel):
    code: str
    name: str
    price_clp: int | None
    revisions: int
    includes: list[str]


class DiagnosticoIn(BaseModel):
    business: str
    email: str
    commune: str
    category: str
    consent: bool
    consent_text: str
    website_url: str | None = None
    honeypot: str = ""
    turnstile_token: str = ""

    @field_validator("business", "commune", "category", "consent_text")
    @classmethod
    def _text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("email")
    @classmethod
    def _mail(cls, value: str) -> str:
        return _email(value)

    @field_validator("website_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ContactoIn(BaseModel):
    name: str
    email: str
    message: str
    consent: bool
    honeypot: str = ""
    turnstile_token: str = ""

    @field_validator("name", "message")
    @classmethod
    def _text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("email")
    @classmethod
    def _mail(cls, value: str) -> str:
        return _email(value)


class DerechosIn(BaseModel):
    kind: str
    email: str
    details: str
    honeypot: str = ""
    turnstile_token: str = ""

    @field_validator("kind", "details")
    @classmethod
    def _text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("email")
    @classmethod
    def _mail(cls, value: str) -> str:
        return _email(value)


class CheckoutIn(BaseModel):
    package_code: str
    lead_id: str | None = None

    @field_validator("package_code")
    @classmethod
    def _code(cls, value: str) -> str:
        return _required_text(value)


class CheckoutOut(BaseModel):
    order_id: str
    checkout_url: str


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _mail(cls, value: str) -> str:
        return _email(value)


class UserOut(BaseModel):
    email: str


class BajaIn(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def _token(cls, value: str) -> str:
        return _required_text(value)


class LeadOut(BaseModel):
    id: str
    business: str
    category: str
    city: str
    commune: str
    status: str
    source: str
    estimated_value_clp: int = 0
    high_value: bool = False
    opportunity_score: int = 0
    paused_from: str | None = None


class MessageOut(BaseModel):
    id: str
    lead_id: str
    channel: str
    direction: str
    status: str
    subject: str | None = None
    body_text: str
    check_result: Any = None


class LeadDetail(LeadOut):
    timeline: list[dict[str, Any]]
    messages: list[MessageOut]
    artifacts: list[dict[str, Any]]
    website_audit: Any = None
    diagnosis: Any = None


class LeadPage(BaseModel):
    items: list[LeadOut]
    page: int
    page_size: int
    total: int


class LeadPatch(BaseModel):
    tone: str | None = None
    next_action_at: datetime | None = None


class TransitionIn(BaseModel):
    to: str
    reason: str

    @field_validator("to", "reason")
    @classmethod
    def _text(cls, value: str) -> str:
        return _required_text(value)


class ApprovalOut(BaseModel):
    id: str
    lead_id: str
    kind: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RejectIn(BaseModel):
    note: str | None = None


class EditIn(BaseModel):
    body_text: str | None = None
    subject: str | None = None
    message_id: str | None = None


class ThreadOut(BaseModel):
    id: str
    lead_id: str
    last_message: str


class ReplyIn(BaseModel):
    body_text: str

    @field_validator("body_text")
    @classmethod
    def _text(cls, value: str) -> str:
        return _required_text(value)


class AgentStatus(BaseModel):
    name: str
    prompt_name: str
    prompt_version: str
    prompt_markdown: str
    last_run_at: str | None = None
    last_error: str | None = None


class EventOut(BaseModel):
    id: str
    ts: str
    agent: str
    level: str
    message: str
    lead_id: str | None = None


class MetricsOut(BaseModel):
    revenue_clp: int
    llm_cost_usd: float
    tokens_today: int
    response_rate_by_channel: dict[str, float]
    funnel: dict[str, int]
    pipeline: dict[str, int]
    quotas: dict[str, Any]


class OrderOut(BaseModel):
    id: str
    lead_id: str
    package_code: str
    status: str
    total_clp: int


class ProjectOut(BaseModel):
    id: str
    status: str
    revisions_used: int
    max_revisions: int
    domain: str | None = None
    deploy_url: str | None = None
    portal_token: str


class ProjectPublic(BaseModel):
    status: str
    business: str
    revisions_used: int
    max_revisions: int
    preview_url: str | None = None


class SettingsOut(BaseModel):
    kill_switch: bool
    app_mode: str
    quotas: dict[str, Any]
    prices: dict[str, Any]
    hitl_response_rate_by_channel: dict[str, Any]


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kill_switch: bool
    app_mode: str | None = None
    quotas: dict[str, Any] | None = None
    prices: dict[str, Any] | None = None
    hitl_response_rate_by_channel: dict[str, float] | None = None


class SuppressionIn(BaseModel):
    kind: str
    value: str
    reason: str

    @field_validator("kind", "value", "reason")
    @classmethod
    def _text(cls, value: str) -> str:
        return _required_text(value)


class DataRequestPatch(BaseModel):
    id: str
    status: str

    @field_validator("id", "status")
    @classmethod
    def _text(cls, value: str) -> str:
        return _required_text(value)


class FeedbackIn(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, value: str) -> str:
        return _required_text(value)
