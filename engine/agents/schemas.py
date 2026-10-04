"""Salidas JSON de los prompts v2. El test las compara con el markdown."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PackageCode = Literal["landing_esencial", "landing_pro", "landing_premium", "multi_sede"]
Tone = Literal["tu", "usted"]
PitchChannel = Literal["email_outreach", "instagram", "linkedin"]
MobileIntentName = Literal[
    "interesado",
    "pregunta_precio",
    "pregunta_detalle",
    "objecion_tiempo",
    "objecion_precio",
    "agendar",
    "no_interesado",
    "opt_out",
    "fuera_de_oficina",
    "rebote",
    "otro",
]


class ScoutLeadDraft(BaseModel):
    business: str
    category: str
    commune: str
    city: str
    estimated_value_clp: int
    high_value: bool
    reason: str


class ScoutOutput(BaseModel):
    leads: list[ScoutLeadDraft]


class Opportunity(BaseModel):
    title: str
    detail: str


class PersonalizationFact(BaseModel):
    field: str
    text: str


class DiagnosisOutput(BaseModel):
    gap_summary: str
    opportunities: list[Opportunity]
    recommended_package: PackageCode
    tone: Tone
    personalization_facts: list[PersonalizationFact]
    pitch_subject: str
    pitch_body: str


class ServiceItem(BaseModel):
    title: str
    detail: str


class FaqItem(BaseModel):
    question: str
    answer: str


class LandingCopy(BaseModel):
    hero_title: str
    hero_subtitle: str
    services: list[ServiceItem]
    faqs: list[FaqItem]
    about: str


class Shot(BaseModel):
    start_s: int
    end_s: int
    visual: str
    on_screen: str


class FilmerOutput(BaseModel):
    duration_s: int
    shots: list[Shot]
    voiceover: str


class LayerResult(BaseModel):
    approved: bool
    score: int
    reasons: list[str]


class CheckerOutput(BaseModel):
    approved: bool
    disagreement: bool
    layer1: LayerResult
    layer2: LayerResult


class JudgeVerdict(BaseModel):
    approved: bool
    score: int
    reasons: list[str]
    fallback: bool


class PitchPlan(BaseModel):
    channel: PitchChannel
    subject: str
    body_text: str
    manual: bool


class MobileIntent(BaseModel):
    intent: MobileIntentName
    confidence: float
    reasons: list[str]


class MobileReply(BaseModel):
    intent: MobileIntentName
    confidence: float
    reply: str
    needs_human: bool


class ProposalOutput(BaseModel):
    title: str
    scope: list[str]
    timeline: str
    revisions: int
    price_clp: int
    includes_iva: bool
    deposit_percent: int


class DeliveryNote(BaseModel):
    portal_path: str
    summary: str
    pending_items: list[str]


class DailyDigest(BaseModel):
    leads_by_status: dict[str, int] = Field(default_factory=dict)
    pending_approvals: int
    llm_spend_usd: float
    summary: str


class CycleDecision(BaseModel):
    ran_scout: bool
    advanced: int
    notes: list[str]


PROMPT_MODELS: dict[str, type[BaseModel]] = {
    "scout": ScoutOutput,
    "diagnoser": DiagnosisOutput,
    "builder": LandingCopy,
    "filmer": FilmerOutput,
    "checker": CheckerOutput,
    "checker_judge": JudgeVerdict,
    "pitcher": PitchPlan,
    "mobile": MobileReply,
    "mobile_classifier": MobileIntent,
    "closer": ProposalOutput,
    "delivery": DeliveryNote,
    "reporter": DailyDigest,
    "orchestrator": CycleDecision,
}
