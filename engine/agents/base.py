"""Base: modelo Lead, estado en filesystem (JSON), logs y utilidades."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

# Raíz del proyecto: .../Agente-IA-Autonomo
ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
OUTPUT_DIR = ROOT / "output"
PROMPTS_DIR = ROOT / "prompts"

LEADS_FILE = STATE_DIR / "leads.json"
LOGS_FILE = STATE_DIR / "logs.json"
QUEUE_FILE = STATE_DIR / "queue.json"

MAX_LOGS = 200
HIGH_VALUE_CLP = 2_800_000  # ~3.000 USD


class LeadStatus(str, Enum):
    NUEVO = "nuevo"
    DIAGNOSTICADO = "diagnosticado"
    LANDING = "landing"
    VIDEO = "video"
    PITCH_LISTO = "pitch_listo"
    ENVIADO = "enviado"
    RESPONDIO = "respondio"
    AGENDADO = "agendado"
    CERRADO = "cerrado"
    REVISION = "revision"


VALID_TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NUEVO: {LeadStatus.DIAGNOSTICADO, LeadStatus.REVISION},
    LeadStatus.DIAGNOSTICADO: {LeadStatus.LANDING, LeadStatus.REVISION},
    LeadStatus.LANDING: {LeadStatus.VIDEO, LeadStatus.REVISION},
    LeadStatus.VIDEO: {LeadStatus.PITCH_LISTO, LeadStatus.REVISION},
    LeadStatus.PITCH_LISTO: {LeadStatus.ENVIADO, LeadStatus.REVISION},
    LeadStatus.ENVIADO: {LeadStatus.RESPONDIO, LeadStatus.CERRADO, LeadStatus.REVISION},
    LeadStatus.RESPONDIO: {LeadStatus.AGENDADO, LeadStatus.CERRADO, LeadStatus.REVISION},
    LeadStatus.AGENDADO: {LeadStatus.CERRADO, LeadStatus.REVISION},
    LeadStatus.CERRADO: set(),
    LeadStatus.REVISION: {
        LeadStatus.DIAGNOSTICADO,
        LeadStatus.LANDING,
        LeadStatus.VIDEO,
        LeadStatus.PITCH_LISTO,
        LeadStatus.ENVIADO,
        LeadStatus.CERRADO,
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str = "lead") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class Lead(BaseModel):
    id: str = Field(default_factory=lambda: new_id("lead"))
    business: str
    category: str
    city: str
    commune: str
    has_website: bool = False
    website_year: Optional[int] = None
    rating: float = 0.0
    reviews: int = 0
    status: LeadStatus = LeadStatus.NUEVO
    estimated_value_clp: int = 350_000
    diagnosis: Optional[str] = None
    pitch: Optional[str] = None
    reason: Optional[str] = None
    landing_path: Optional[str] = None
    video_path: Optional[str] = None
    storyboard: Optional[str] = None
    check_result: Optional[dict[str, Any]] = None
    send_simulation: Optional[dict[str, Any]] = None
    channels: list[str] = Field(default_factory=list)
    contact_hint: Optional[str] = None  # solo pistas públicas, no inventar datos privados
    high_value: bool = False
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def maybe_escalate_high_value(self) -> bool:
        """Si valor >= umbral HITL, marca revision. Retorna True si escaló."""
        if self.estimated_value_clp >= HIGH_VALUE_CLP:
            self.high_value = True
            self.status = LeadStatus.REVISION
            self.reason = (
                self.reason or ""
            ) + f" | Deal {self.estimated_value_clp:,} CLP → revisión manual (HITL)".replace(",", ".")
            self.touch()
            return True
        return False


def ensure_state_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not LEADS_FILE.exists():
        LEADS_FILE.write_text("[]", encoding="utf-8")
    if not LOGS_FILE.exists():
        LOGS_FILE.write_text("[]", encoding="utf-8")
    if not QUEUE_FILE.exists():
        QUEUE_FILE.write_text('{"pending": [], "priority": []}', encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    ensure_state_dirs()
    if not path.exists():
        return default
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return default
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, data: Any) -> None:
    ensure_state_dirs()
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_leads() -> list[Lead]:
    data = read_json(LEADS_FILE, [])
    leads: list[Lead] = []
    for item in data:
        try:
            leads.append(Lead.model_validate(item))
        except Exception:
            continue
    return leads


def save_leads(leads: list[Lead]) -> None:
    write_json(LEADS_FILE, [lead.model_dump(mode="json") for lead in leads])


def get_lead(lead_id: str) -> Optional[Lead]:
    for lead in load_leads():
        if lead.id == lead_id:
            return lead
    return None


def upsert_lead(lead: Lead) -> Lead:
    leads = load_leads()
    found = False
    for i, existing in enumerate(leads):
        if existing.id == lead.id:
            lead.touch()
            leads[i] = lead
            found = True
            break
    if not found:
        lead.touch()
        leads.append(lead)
    save_leads(leads)
    return lead


def upsert_leads(batch: list[Lead]) -> list[Lead]:
    leads = load_leads()
    by_id = {l.id: i for i, l in enumerate(leads)}
    for lead in batch:
        lead.touch()
        if lead.id in by_id:
            leads[by_id[lead.id]] = lead
        else:
            by_id[lead.id] = len(leads)
            leads.append(lead)
    save_leads(leads)
    return batch


def log_event(agent: str, message: str, level: str = "info", meta: Optional[dict] = None) -> dict:
    """Append-only log; más reciente primero; máx MAX_LOGS."""
    logs = read_json(LOGS_FILE, [])
    if not isinstance(logs, list):
        logs = []
    entry = {
        "id": new_id("log"),
        "ts": utc_now_iso(),
        "agent": agent,
        "level": level,
        "message": message,
        "meta": meta or {},
    }
    logs.insert(0, entry)
    logs = logs[:MAX_LOGS]
    write_json(LOGS_FILE, logs)
    return entry


def load_logs(limit: int = 20) -> list[dict]:
    logs = read_json(LOGS_FILE, [])
    if not isinstance(logs, list):
        return []
    return logs[:limit]


def read_prompt(name: str) -> str:
    """Lee prompts/<name>.md (sin extensión o con .md)."""
    stem = name.replace(".md", "")
    path = PROMPTS_DIR / f"{stem}.md"
    if not path.exists():
        return f"[Prompt no encontrado: {stem}.md]"
    return path.read_text(encoding="utf-8")


def list_prompts() -> list[str]:
    if not PROMPTS_DIR.exists():
        return []
    return sorted(p.name for p in PROMPTS_DIR.glob("*.md"))


def leads_by_status(status: LeadStatus | str) -> list[Lead]:
    s = LeadStatus(status) if isinstance(status, str) else status
    return [l for l in load_leads() if l.status == s]


def status_counts() -> dict[str, int]:
    counts: dict[str, int] = {s.value: 0 for s in LeadStatus}
    for lead in load_leads():
        counts[lead.status.value] = counts.get(lead.status.value, 0) + 1
    return counts


class StateManager:
    """Fachada simple sobre el estado filesystem."""

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
    def log(agent: str, message: str, level: str = "info", meta: Optional[dict] = None) -> dict:
        return log_event(agent, message, level, meta)

    @staticmethod
    def counts() -> dict[str, int]:
        return status_counts()
