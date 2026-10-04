"""Migración JSON: corrupto aborta; inválidos se reportan; el origen no se reescribe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from core.config import reset_settings
from db import migrate_json
from db.models import Event, Lead
from db.session import reset_engine, session_scope


@pytest.fixture(autouse=True)
def _caches() -> object:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    leads: Any,
    logs: Any,
    *,
    raw_leads: bytes | None = None,
) -> tuple[Path, Path, Path, Path]:
    leads_path = tmp_path / "leads.json"
    logs_path = tmp_path / "logs.json"
    backup = tmp_path / "backup"
    db_path = tmp_path / "agencia.db"
    if raw_leads is None:
        leads_path.write_text(json.dumps(leads, ensure_ascii=False), encoding="utf-8")
    else:
        leads_path.write_bytes(raw_leads)
    if isinstance(logs, bytes):
        logs_path.write_bytes(logs)
    else:
        logs_path.write_text(json.dumps(logs, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(migrate_json, "LEADS_FILE", leads_path)
    monkeypatch.setattr(migrate_json, "LOGS_FILE", logs_path)
    monkeypatch.setattr(migrate_json, "BACKUP_DIR", backup)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    reset_settings()
    reset_engine()
    return leads_path, logs_path, backup, db_path


def _valid(lead_id: str, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": lead_id,
        "business": f"Negocio {lead_id}",
        "category": "cafeteria",
        "city": "Santiago",
        "commune": "Providencia",
        "status": "nuevo",
        "estimated_value_clp": 250_000,
    }
    data.update(extra)
    return data


def test_json_corrupto_sale_1_y_no_toca_el_archivo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leads_path, logs_path, backup, db_path = _prepare(
        tmp_path,
        monkeypatch,
        None,
        [],
        raw_leads=b"{esto no es json",
    )
    before_leads = leads_path.read_bytes()
    before_logs = logs_path.read_bytes()
    assert migrate_json.main() == 1
    assert leads_path.read_bytes() == before_leads
    assert logs_path.read_bytes() == before_logs
    assert not db_path.exists()
    assert not backup.exists()


def test_lead_invalido_no_se_inserta_y_la_segunda_corrida_no_duplica(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    leads = [
        _valid("ok1", business="Café Andes", has_website=False, pitch="hola"),
        {"id": "bad1", "business": ""},
        _valid(
            "out1",
            business="Estudio Norte",
            category="abogados",
            status="cerrado",
            reason="No interesado, gracias",
            estimated_value_clp=450_000,
        ),
        _valid(
            "drop1",
            business="Local Sur",
            status="cerrado",
            reason="Descartado",
        ),
        _valid(
            "old1",
            business="Taller Centro",
            status="cerrado",
            reason="no contestó",
        ),
    ]
    logs = [
        {
            "id": "log1",
            "ts": "2026-10-04T15:00:00+00:00",
            "agent": "scout",
            "level": "info",
            "message": "lead creado",
            "meta": {"lead_id": "ok1"},
        },
        {"id": "badlog", "level": "fatal", "message": "no"},
    ]
    leads_path, logs_path, backup, _db_path = _prepare(tmp_path, monkeypatch, leads, logs)
    before_leads = leads_path.read_bytes()
    before_logs = logs_path.read_bytes()

    assert migrate_json.main() == 0
    first_out = capsys.readouterr().out
    assert "invalido lead" in first_out
    assert "leads_invalidos=1" in first_out
    assert "events_invalidos=1" in first_out
    assert leads_path.read_bytes() == before_leads
    assert logs_path.read_bytes() == before_logs
    assert any(backup.iterdir())

    with session_scope() as current:
        rows = {row.id: row for row in current.scalars(select(Lead)).all()}
        assert set(rows) == {"ok1", "out1", "drop1", "old1"}
        assert "bad1" not in rows
        assert rows["ok1"].source == "outbound_demo"
        assert rows["ok1"].opportunity_score == 0
        assert rows["ok1"].tone == "tu"
        assert rows["ok1"].diagnosis["legacy"]["pitch"] == "hola"
        assert rows["out1"].status == "opt_out"
        assert rows["out1"].tone == "usted"
        assert rows["drop1"].status == "perdido"
        assert rows["drop1"].close_reason == "descartado"
        assert rows["old1"].status == "perdido"
        assert rows["old1"].close_reason == "legacy_cerrado"
        events = list(current.scalars(select(Event)).all())
        assert len(events) == 1
        assert events[0].lead_id == "ok1"
        assert current.scalar(select(func.count()).select_from(Lead)) == 4

    assert migrate_json.main() == 0
    second_out = capsys.readouterr().out
    assert "leads_ya_existentes=4" in second_out
    assert leads_path.read_bytes() == before_leads
    with session_scope() as current:
        assert current.scalar(select(func.count()).select_from(Lead)) == 4
        assert current.scalar(select(func.count()).select_from(Event)) == 1
