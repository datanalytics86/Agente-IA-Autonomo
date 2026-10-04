"""Migra leads.json y logs.json a la base. No reescribe los archivos de origen."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select

from core.config import get_settings
from core.states import RESUMABLE, STATUSES
from db.models import Event, Lead
from db.normalize import normalize_contact
from db.session import create_all, reset_engine, session_scope

ENGINE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = ENGINE_DIR / "state"
LEADS_FILE = STATE_DIR / "leads.json"
LOGS_FILE = STATE_DIR / "logs.json"
BACKUP_DIR = STATE_DIR / "backup"

SOURCES = frozenset(
    {
        "outbound_places",
        "outbound_demo",
        "inbound_diagnostico",
        "inbound_contacto",
        "inbound_whatsapp",
        "referido",
    }
)
FORMAL_CATEGORIES = frozenset({"clinica-dental", "optica", "abogados", "estudio-contable"})
_LEVELS = frozenset({"debug", "info", "warn", "error"})
_LEGACY_KEYS = (
    "has_website",
    "website_year",
    "pitch",
    "reason",
    "landing_path",
    "video_path",
    "storyboard",
    "check_result",
    "send_simulation",
    "channels",
    "contact_hint",
)


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class LegacyLead(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    business: str = Field(min_length=1)
    category: str = Field(min_length=1)
    city: str = Field(min_length=1)
    commune: str = Field(min_length=1)
    status: str
    source: str | None = None
    estimated_value_clp: int = Field(ge=0)
    opportunity_score: int | None = Field(default=None, ge=0, le=100)
    high_value: bool | None = None
    tone: str | None = None
    place_id: str | None = None
    google_maps_uri: str | None = None
    website_url: str | None = None
    website_audit: dict[str, Any] | None = None
    rating: float | None = None
    reviews: int | None = None
    contact_email: str | None = None
    contact_email_source_url: str | None = None
    instagram_handle: str | None = None
    linkedin_url: str | None = None
    phone_public: str | None = None
    consent: dict[str, Any] | None = None
    paused_from: str | None = None
    hitl_reason: str | None = None
    close_reason: str | None = None
    diagnosis: str | dict[str, Any] | None = None
    next_action_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    anonymized_at: str | None = None
    address_public: str | None = None
    has_website: bool | None = None
    website_year: int | None = None
    pitch: str | None = None
    reason: str | None = None
    landing_path: str | None = None
    video_path: str | None = None
    storyboard: str | None = None
    check_result: dict[str, Any] | None = None
    send_simulation: dict[str, Any] | None = None
    channels: list[str] | None = None
    contact_hint: str | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        if value not in STATUSES and value != "cerrado":
            raise ValueError("status desconocido")
        return value

    @field_validator("source")
    @classmethod
    def _source(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        if value not in SOURCES:
            raise ValueError("source desconocido")
        return value

    @field_validator("tone", "paused_from")
    @classmethod
    def _optional_token(cls, value: str | None, info: Any) -> str | None:
        if value is None or value.strip() == "":
            return None
        if info.field_name == "tone" and value not in {"tu", "usted"}:
            raise ValueError("tone debe ser tu o usted")
        if info.field_name == "paused_from" and value not in RESUMABLE:
            raise ValueError("paused_from desconocido")
        return value

    @field_validator(
        "place_id",
        "contact_email",
        "website_url",
        "phone_public",
        "linkedin_url",
        "google_maps_uri",
        "address_public",
        "contact_email_source_url",
        "instagram_handle",
        mode="before",
    )
    @classmethod
    def _blank(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("created_at", "updated_at", "anonymized_at", "next_action_at")
    @classmethod
    def _timestamps(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        _parse_ts(value)
        return value


class LegacyLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    message: str
    agent: str = Field(default="legacy", min_length=1)
    level: str = "info"
    ts: str | None = None
    meta: dict[str, Any] | None = None

    @field_validator("level")
    @classmethod
    def _level(cls, value: str) -> str:
        if value not in _LEVELS:
            raise ValueError("level desconocido")
        return value

    @field_validator("ts")
    @classmethod
    def _ts(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        _parse_ts(value)
        return value


def main() -> int:
    """Copia el JSON, inserta lo válido y deja el origen intacto.

    Si un archivo no parsea, sale 1 sin abrir la base y sin modificar el archivo.
    """
    leads_raw, leads_error = _read_array(LEADS_FILE)
    logs_raw, logs_error = _read_array(LOGS_FILE)
    errors = [item for item in (leads_error, logs_error) if item]
    if errors:
        print("error json ilegible: " + "; ".join(errors))
        return 1

    _backup(LEADS_FILE, LOGS_FILE)
    create_all()
    assert leads_raw is not None
    assert logs_raw is not None
    try:
        summary = _import(leads_raw, logs_raw)
    finally:
        reset_engine()
    print(
        "resumen "
        f"leads_ok={summary[0]} leads_invalidos={summary[1]} "
        f"leads_ya_existentes={summary[2]} "
        f"events_ok={summary[3]} events_invalidos={summary[4]} "
        f"events_ya_existentes={summary[5]}"
    )
    return 0


def _read_array(path: Path) -> tuple[list[Any] | None, str | None]:
    if not path.exists():
        return [], None
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, f"{path.name}: encoding"
    if not text.strip():
        return None, f"{path.name}: vacío"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, f"{path.name}: json"
    if not isinstance(data, list):
        return None, f"{path.name}: se esperaba un array"
    return data, None


def _backup(leads_path: Path, logs_path: Path) -> None:
    existing = [path for path in (leads_path, logs_path) if path.exists()]
    if not existing:
        return
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    dest = BACKUP_DIR / stamp
    dest.mkdir(parents=True, exist_ok=False)
    for path in existing:
        shutil.copy2(path, dest / path.name)


def _import(
    leads_raw: list[Any],
    logs_raw: list[Any],
) -> tuple[int, int, int, int, int, int]:
    leads_ok = leads_bad = leads_skip = 0
    events_ok = events_bad = events_skip = 0
    with session_scope() as session:
        existing_leads = set(session.scalars(select(Lead.id)).all())
        existing_events = set(session.scalars(select(Event.id)).all())
        staged_leads: set[str] = set()
        staged_events: set[str] = set()

        for index, item in enumerate(leads_raw):
            lead_id = _item_id(item)
            if not isinstance(item, dict):
                leads_bad += 1
                print(f"invalido lead indice={index} id={lead_id} motivo=no es un objeto")
                continue
            try:
                parsed = LegacyLead.model_validate(item)
            except ValidationError as exc:
                leads_bad += 1
                print(f"invalido lead indice={index} id={lead_id} motivo={_motivo(exc)}")
                continue
            if parsed.id in existing_leads or parsed.id in staged_leads:
                leads_skip += 1
                continue
            session.add(_to_lead(parsed))
            staged_leads.add(parsed.id)
            leads_ok += 1
        session.flush()

        known_leads = existing_leads | staged_leads
        for index, item in enumerate(logs_raw):
            event_id = _item_id(item)
            if not isinstance(item, dict):
                events_bad += 1
                print(f"invalido event indice={index} id={event_id} motivo=no es un objeto")
                continue
            try:
                parsed_log = LegacyLog.model_validate(item)
            except ValidationError as exc:
                events_bad += 1
                print(f"invalido event indice={index} id={event_id} motivo={_motivo(exc)}")
                continue
            if parsed_log.id in existing_events or parsed_log.id in staged_events:
                events_skip += 1
                continue
            session.add(_to_event(parsed_log, known_leads))
            staged_events.add(parsed_log.id)
            events_ok += 1
    return leads_ok, leads_bad, leads_skip, events_ok, events_bad, events_skip


def _motivo(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(part) for part in err["loc"])
    return f"{loc}: {err['msg']}"


def _item_id(item: object) -> str:
    if isinstance(item, dict):
        raw = item.get("id")
        if isinstance(raw, str) and raw.strip():
            return raw
    return "-"


def _map_status(item: LegacyLead) -> tuple[str, str | None]:
    if item.status != "cerrado":
        return item.status, item.close_reason
    text = (item.reason or "").strip()
    low = text.lower()
    if "no interesado" in low or "opt-out" in low or "opt_out" in low or low == "opt out":
        return "opt_out", None
    if low in {"descartado", "reject"}:
        return "perdido", "descartado"
    return "perdido", "legacy_cerrado"


def _to_lead(item: LegacyLead) -> Lead:
    status, close_reason = _map_status(item)
    now = datetime.now(UTC)
    created = _parse_ts(item.created_at) if item.created_at else now
    updated = _parse_ts(item.updated_at) if item.updated_at else created
    high = item.high_value
    if high is None:
        high = item.estimated_value_clp >= get_settings().hitl_value_clp
    tone = item.tone or ("usted" if item.category in FORMAL_CATEGORIES else "tu")
    instagram = item.instagram_handle
    if instagram:
        instagram = normalize_contact("instagram", instagram)
    score = item.opportunity_score if item.opportunity_score is not None else 0
    paused = item.paused_from if status == "revision" else None
    return Lead(
        id=item.id,
        source=item.source or "outbound_demo",
        business=item.business,
        category=item.category,
        city=item.city,
        commune=item.commune,
        address_public=item.address_public,
        place_id=item.place_id,
        google_maps_uri=item.google_maps_uri,
        website_url=item.website_url,
        website_audit=item.website_audit,
        opportunity_score=score,
        rating=item.rating,
        reviews=item.reviews,
        contact_email=item.contact_email,
        contact_email_source_url=item.contact_email_source_url,
        instagram_handle=instagram,
        linkedin_url=item.linkedin_url,
        phone_public=item.phone_public,
        consent=item.consent,
        status=status,
        paused_from=paused,
        hitl_reason=item.hitl_reason,
        close_reason=close_reason,
        estimated_value_clp=item.estimated_value_clp,
        high_value=high,
        tone=tone,
        diagnosis=_diagnosis(item),
        next_action_at=_parse_ts(item.next_action_at) if item.next_action_at else None,
        created_at=created,
        updated_at=updated,
        anonymized_at=_parse_ts(item.anonymized_at) if item.anonymized_at else None,
    )


def _diagnosis(item: LegacyLead) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    if isinstance(item.diagnosis, str):
        payload["markdown"] = item.diagnosis
    elif isinstance(item.diagnosis, dict):
        payload.update(item.diagnosis)
    legacy = {key: getattr(item, key) for key in _LEGACY_KEYS if getattr(item, key) is not None}
    if legacy:
        payload["legacy"] = legacy
    return payload or None


def _to_event(item: LegacyLog, known_leads: set[str]) -> Event:
    meta = dict(item.meta or {})
    raw_lead = meta.get("lead_id")
    lead_id = raw_lead if isinstance(raw_lead, str) and raw_lead in known_leads else None
    return Event(
        id=item.id,
        ts=_parse_ts(item.ts) if item.ts else datetime.now(UTC),
        agent=item.agent,
        level=item.level,
        message=item.message,
        lead_id=lead_id,
        meta=meta or None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
