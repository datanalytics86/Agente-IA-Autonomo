"""Lead de proyección, prompts y lectura de estado. La fuente es la base."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agents.catalog import CATEGORY_SLUGS
from agents.runtime import OUTPUT_DIR, ROOT, iter_leads, log_event, prepare_db
from db.models import Lead as DbLead
from db.repositories import ArtifactRepository, EventRepository, LeadRepository, MessageRepository
from db.session import session_scope

STATE_DIR = ROOT / "state"
PROMPTS_DIR = ROOT / "prompts"
LEADS_FILE = STATE_DIR / "leads.json"
LOGS_FILE = STATE_DIR / "logs.json"


class LeadStatus(StrEnum):
    NUEVO = "nuevo"
    DIAGNOSTICADO = "diagnosticado"
    LANDING = "landing"
    VIDEO = "video"
    PITCH_LISTO = "pitch_listo"
    ENVIADO = "enviado"
    RESPONDIO = "respondio"
    AGENDADO = "agendado"
    PROPUESTA = "propuesta"
    PAGADO = "pagado"
    EN_PRODUCCION = "en_produccion"
    EN_REVISION_CLIENTE = "en_revision_cliente"
    ENTREGADO = "entregado"
    POSTVENTA = "postventa"
    REVISION = "revision"
    PERDIDO = "perdido"
    OPT_OUT = "opt_out"
    CERRADO = "cerrado"


class InvalidLeadsError(ValueError):
    """Hay leads que no se pueden proyectar. No se descartan en silencio."""

    def __init__(self, invalid: list[dict[str, Any]]) -> None:
        self.invalid = invalid
        super().__init__(f"{len(invalid)} lead(s) inválidos")


class Lead(BaseModel):
    """Proyección que consume el CLI. El estado canónico vive en la base."""

    id: str = Field(default_factory=lambda: f"lead_{uuid.uuid4().hex[:10]}")
    business: str
    category: str
    city: str
    commune: str
    has_website: bool = False
    website_year: int | None = None
    rating: float = 0.0
    reviews: int = 0
    status: LeadStatus = LeadStatus.NUEVO
    estimated_value_clp: int = 350_000
    diagnosis: str | None = None
    pitch: str | None = None
    reason: str | None = None
    landing_path: str | None = None
    video_path: str | None = None
    storyboard: str | None = None
    check_result: dict[str, Any] | None = None
    send_simulation: dict[str, Any] | None = None
    channels: list[str] = Field(default_factory=list)
    contact_hint: str | None = None
    high_value: bool = False
    created_at: str = ""
    updated_at: str = ""

    def touch(self) -> None:
        self.updated_at = datetime.now().astimezone().replace(microsecond=0).isoformat()


def ensure_state_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_if_missing(LEADS_FILE, "[]")
    _write_if_missing(LOGS_FILE, "[]")


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    """Si el JSON no parsea, lanza. No devuelve [] para que nadie lo reescriba."""
    ensure_state_dirs()
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return default
    return json.loads(raw)


def write_json(path: Path, data: Any) -> None:
    ensure_state_dirs()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_leads_from_json(path: Path | None = None) -> list[Lead]:
    target = path or LEADS_FILE
    data = read_json(target, [])
    if not isinstance(data, list):
        raise InvalidLeadsError([{"path": str(target), "error": "el archivo no es una lista"}])
    leads: list[Lead] = []
    invalid: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        try:
            leads.append(Lead.model_validate(item))
        except ValidationError as exc:
            invalid.append({"index": index, "error": str(exc), "item": item})
    if invalid:
        raise InvalidLeadsError(invalid)
    return leads


def project_lead(session: object, row: DbLead) -> Lead:
    """Proyecta con la sesión abierta. No abre otra conexión."""
    from sqlalchemy.orm import Session

    if not isinstance(session, Session):
        raise TypeError("se esperaba una sesión")
    return _project(row, ArtifactRepository(session), MessageRepository(session))


def load_leads() -> list[Lead]:
    """Lee la base y proyecta. Un lead inválido se reporta, no se omite."""
    prepare_db()
    with session_scope() as session:
        artifacts = ArtifactRepository(session)
        messages = MessageRepository(session)
        leads: list[Lead] = []
        invalid: list[dict[str, Any]] = []
        for row in iter_leads(session):
            try:
                leads.append(_project(row, artifacts, messages))
            except ValueError as exc:
                invalid.append(
                    {
                        "id": row.id,
                        "business": row.business,
                        "category": row.category,
                        "status": row.status,
                        "error": str(exc),
                    }
                )
        if invalid:
            raise InvalidLeadsError(invalid)
        return leads


def _project(
    row: DbLead,
    artifacts: ArtifactRepository,
    messages: MessageRepository,
) -> Lead:
    problems: list[str] = []
    if row.category not in CATEGORY_SLUGS:
        problems.append(f"category {row.category!r}")
    if row.status not in {item.value for item in LeadStatus}:
        problems.append(f"status {row.status!r}")
    if not str(row.business or "").strip():
        problems.append("business vacío")
    if problems:
        raise ValueError("; ".join(problems))
    diagnosis = row.diagnosis if isinstance(row.diagnosis, dict) else {}
    audit = row.website_audit if isinstance(row.website_audit, dict) else {}
    markdown = diagnosis.get("markdown")
    if not isinstance(markdown, str):
        markdown = (
            diagnosis.get("gap_summary") if isinstance(diagnosis.get("gap_summary"), str) else None
        )
    pitch = diagnosis.get("pitch_body") if isinstance(diagnosis.get("pitch_body"), str) else None
    landing = _artifact_path(artifacts, row.id, "landing_demo")
    video = _artifact_path(artifacts, row.id, "storyboard")
    storyboard = None
    if video:
        path = Path(video)
        if path.is_file():
            storyboard = path.read_text(encoding="utf-8")
    latest = _latest_outbound(messages, row.id)
    check = latest.check_result if latest is not None else None
    simulation = None
    if latest is not None:
        simulation = {
            "channel": latest.channel,
            "status": latest.status,
            "blocked": latest.status in {"rejected", "blocked", "manual_pending"},
        }
    created = row.created_at.isoformat() if isinstance(row.created_at, datetime) else ""
    updated = row.updated_at.isoformat() if isinstance(row.updated_at, datetime) else ""
    return Lead(
        id=row.id,
        business=row.business,
        category=row.category,
        city=row.city,
        commune=row.commune,
        has_website=bool(row.website_url),
        website_year=audit.get("copyright_year")
        if isinstance(audit.get("copyright_year"), int)
        else None,
        rating=float(row.rating or 0),
        reviews=int(row.reviews or 0),
        status=LeadStatus(row.status),
        estimated_value_clp=row.estimated_value_clp,
        diagnosis=markdown,
        pitch=pitch,
        reason=row.hitl_reason or row.close_reason or audit.get("scout_reason"),
        landing_path=landing,
        video_path=video,
        storyboard=storyboard,
        check_result=check if isinstance(check, dict) else None,
        send_simulation=simulation,
        channels=[latest.channel] if latest is not None else [],
        contact_hint=row.contact_email or row.instagram_handle,
        high_value=bool(row.high_value),
        created_at=created,
        updated_at=updated,
    )


def _artifact_path(artifacts: ArtifactRepository, lead_id: str, kind: str) -> str | None:
    matches = [item for item in artifacts.list(lead_id=lead_id, limit=50) if item.kind == kind]
    if not matches:
        return None
    return matches[-1].path


def _latest_outbound(messages: MessageRepository, lead_id: str) -> Any:
    outbound = [
        item for item in messages.list(lead_id=lead_id, limit=50) if item.direction == "out"
    ]
    if not outbound:
        return None
    return outbound[-1]


def save_leads(leads: list[Lead]) -> None:
    """Escribe el JSON que le pasan. No lee el archivo antes, así no pisa un JSON roto."""
    write_json(LEADS_FILE, [lead.model_dump(mode="json") for lead in leads])


def get_lead(lead_id: str) -> Lead | None:
    for lead in load_leads():
        if lead.id == lead_id:
            return lead
    return None


def upsert_lead(lead: Lead) -> Lead:
    from core.states import transition

    prepare_db()
    lead.touch()
    with session_scope() as session:
        repo = LeadRepository(session)
        current = repo.get(lead.id)
        if current is None:
            created = DbLead(
                id=lead.id,
                source="outbound_demo",
                business=lead.business,
                category=lead.category,
                city=lead.city,
                commune=lead.commune,
                opportunity_score=50,
                status="nuevo",
                estimated_value_clp=lead.estimated_value_clp,
                high_value=lead.high_value,
                tone="tu",
            )
            repo.add(created)
            if lead.status != LeadStatus.NUEVO:
                transition(
                    session,
                    created,
                    lead.status.value,
                    actor="sistema",
                    reason="proyección inicial",
                )
        else:
            current.business = lead.business
            current.category = lead.category
            current.city = lead.city
            current.commune = lead.commune
            current.estimated_value_clp = lead.estimated_value_clp
            current.high_value = lead.high_value
            if current.status != lead.status.value:
                transition(
                    session,
                    current,
                    lead.status.value,
                    actor="sistema",
                    reason="proyección",
                )
            repo.save(current)
    return lead


def upsert_leads(batch: list[Lead]) -> list[Lead]:
    for lead in batch:
        upsert_lead(lead)
    return batch


def load_logs(limit: int = 20) -> list[dict[str, Any]]:
    prepare_db()
    with session_scope() as session:
        rows = EventRepository(session).list(limit=limit)
    if rows:
        return [
            {
                "id": row.id,
                "ts": row.ts.isoformat(),
                "agent": row.agent,
                "level": row.level,
                "message": row.message,
                "meta": row.meta or {},
            }
            for row in rows
        ]
    data = read_json(LOGS_FILE, [])
    if not isinstance(data, list):
        raise InvalidLeadsError([{"path": str(LOGS_FILE), "error": "logs no es una lista"}])
    return data[:limit]


def read_prompt(name: str) -> str:
    stem = name.replace(".md", "")
    path = PROMPTS_DIR / f"{stem}.md"
    if not path.exists():
        return f"[Prompt no encontrado: {stem}.md]"
    return path.read_text(encoding="utf-8")


def list_prompts() -> list[str]:
    if not PROMPTS_DIR.exists():
        return []
    return sorted(path.name for path in PROMPTS_DIR.glob("*.md"))


def leads_by_status(status: LeadStatus | str) -> list[Lead]:
    selected = LeadStatus(status) if isinstance(status, str) else status
    return [lead for lead in load_leads() if lead.status == selected]


def status_counts() -> dict[str, int]:
    counts: dict[str, int] = {item.value: 0 for item in LeadStatus}
    prepare_db()
    with session_scope() as session:
        for row in iter_leads(session):
            counts[row.status] = counts.get(row.status, 0) + 1
    return counts


class StateManager:
    """Fachada. Los agentes nuevos escriben por repositorios."""

    root = ROOT
    state_dir = STATE_DIR
    output_dir = OUTPUT_DIR

    @staticmethod
    def ensure() -> None:
        ensure_state_dirs()

    @staticmethod
    def load_leads() -> list[Lead]:
        return load_leads()

    @staticmethod
    def save_leads(leads: list[Lead]) -> None:
        save_leads(leads)

    @staticmethod
    def upsert(lead: Lead) -> Lead:
        return upsert_lead(lead)

    @staticmethod
    def log(
        agent: str, message: str, level: str = "info", meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return log_event(agent, message, level, meta)

    @staticmethod
    def counts() -> dict[str, int]:
        return status_counts()
