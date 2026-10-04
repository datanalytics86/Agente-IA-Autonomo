"""Proyección de leads, JSON que no se pisa y cero asignaciones de status."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from agents.base import (
    InvalidLeadsError,
    Lead,
    ensure_state_dirs,
    list_prompts,
    load_leads,
    load_leads_from_json,
    load_logs,
    read_json,
    read_prompt,
    status_counts,
)
from agents.pipeline import Orchestrator
from agents.runtime import set_column_status
from agents.scout import run_scout
from core.config import reset_settings
from db.models import Lead as DbLead
from db.repositories import LeadRepository
from db.session import create_all, reset_engine, session_scope

ENGINE = Path(__file__).resolve().parents[1]
_ASSIGN = re.compile(r"\.status\s*=(?!=)")


@pytest.fixture(autouse=True)
def _caches() -> Any:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("OUTREACH_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'base.db').as_posix()}")
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setenv("GROK_API_KEY", "")
    reset_settings()
    reset_engine()
    create_all()
    return tmp_path


def test_nombres_que_importa_main(db: Path) -> None:
    assert Lead is not None
    assert callable(ensure_state_dirs)
    assert callable(list_prompts)
    assert callable(load_leads)
    assert callable(load_logs)
    assert callable(read_prompt)
    assert callable(status_counts)
    assert callable(Orchestrator().run_demo)
    assert callable(run_scout)


def test_json_invalido_no_se_reescribe(tmp_path: Path) -> None:
    path = tmp_path / "leads.json"
    raw = "{esto no es json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        read_json(path, [])
    with pytest.raises(json.JSONDecodeError):
        load_leads_from_json(path)
    assert path.read_text(encoding="utf-8") == raw


def test_json_con_items_invalidos_se_reporta(tmp_path: Path) -> None:
    path = tmp_path / "leads.json"
    payload = [{"business": "sin el resto"}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(InvalidLeadsError) as exc:
        load_leads_from_json(path)
    assert exc.value.invalid
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_load_leads_reporta_filas_invalidas(db: Path) -> None:
    with session_scope() as session:
        LeadRepository(session).add(
            DbLead(
                source="outbound_demo",
                business="Negocio Roto",
                category="no-es-rubro",
                city="Santiago",
                commune="Providencia",
                opportunity_score=40,
                status="nuevo",
                estimated_value_clp=250_000,
                high_value=False,
                tone="tu",
            )
        )
    with pytest.raises(InvalidLeadsError) as exc:
        load_leads()
    assert exc.value.invalid[0]["category"] == "no-es-rubro"
    assert "category" in exc.value.invalid[0]["error"]


def test_agents_no_asignan_status() -> None:
    offenders: list[str] = []
    root = ENGINE / "agents"
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        for match in _ASSIGN.finditer(text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.name}:{line}")
    assert offenders == []


def test_set_column_status_rechaza_el_lead() -> None:
    lead = DbLead(
        source="outbound_demo",
        business="Café Andes",
        category="cafeteria",
        city="Santiago",
        commune="Providencia",
        opportunity_score=50,
        status="nuevo",
        estimated_value_clp=250_000,
        high_value=False,
        tone="tu",
    )
    with pytest.raises(RuntimeError):
        set_column_status(lead, "enviado")
    assert lead.status == "nuevo"
