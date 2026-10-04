"""La máquina de estados rechaza aristas ilegales y no toca el status."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import reset_settings
from core.errors import TransitionError
from core.hitl import channel_should_pause, response_rate
from core.states import transition
from db.models import Lead, LeadEvent
from db.repositories import (
    EventRepository,
    LeadRepository,
    SettingsRepository,
    SuppressionRepository,
)
from db.session import create_all, reset_engine, session_scope


@pytest.fixture(autouse=True)
def _caches() -> object:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    url = f"sqlite:///{(tmp_path / 'states.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_settings()
    reset_engine()
    create_all()
    with session_scope() as current:
        yield current


def make_lead(**overrides: Any) -> Lead:
    suffix = overrides.get("id") or datetime.now(UTC).strftime("%H%M%S%f")
    data: dict[str, Any] = {
        "source": "outbound_demo",
        "business": f"Negocio {suffix}",
        "category": "cafeteria",
        "city": "Santiago",
        "commune": "Ñuñoa",
        "opportunity_score": 60,
        "status": "nuevo",
        "estimated_value_clp": 350_000,
        "high_value": False,
        "tone": "tu",
    }
    data.update(overrides)
    return Lead(**data)


def test_transicion_ilegal_no_cambia_status(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead())
    with pytest.raises(TransitionError):
        transition(session, lead, "enviado", actor="agente", reason="salto")
    assert lead.status == "nuevo"
    assert list(session.scalars(select(LeadEvent)).all()) == []


def test_revision_a_enviado_es_ilegal(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead(status="pitch_listo"))
    transition(session, lead, "revision", actor="humano", reason="revisar pitch")
    assert lead.status == "revision"
    assert lead.paused_from == "pitch_listo"
    with pytest.raises(TransitionError):
        transition(
            session,
            lead,
            "enviado",
            actor="agente",
            reason="atajo",
            checker_approved=True,
        )
    assert lead.status == "revision"
    transition(session, lead, "paused_from", actor="humano", reason="aprobado")
    assert lead.status == "pitch_listo"
    assert lead.paused_from is None


def test_pitch_listo_exige_checker(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead(status="pitch_listo"))
    with pytest.raises(TransitionError):
        transition(session, lead, "enviado", actor="agente", reason="sin checker")
    assert lead.status == "pitch_listo"
    transition(
        session,
        lead,
        "enviado",
        actor="agente",
        reason="checker ok",
        checker_approved=True,
    )
    assert lead.status == "enviado"
    events = EventRepository(session).list(lead_id=lead.id)
    assert events[0].level == "info"
    rows = list(session.scalars(select(LeadEvent).where(LeadEvent.lead_id == lead.id)).all())
    assert rows[-1].from_status == "pitch_listo"
    assert rows[-1].to_status == "enviado"
    assert rows[-1].actor == "agente"


def test_landing_a_pitch_solo_sin_video(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEO_ENABLED", "true")
    reset_settings()
    blocked = LeadRepository(session).add(make_lead(status="landing"))
    with pytest.raises(TransitionError):
        transition(session, blocked, "pitch_listo", actor="agente", reason="sin video")
    assert blocked.status == "landing"
    transition(session, blocked, "video", actor="agente", reason="filmer")
    assert blocked.status == "video"

    monkeypatch.setenv("VIDEO_ENABLED", "false")
    reset_settings()
    opened = LeadRepository(session).add(make_lead(status="landing", business="Otro local"))
    transition(session, opened, "pitch_listo", actor="agente", reason="video apagado")
    assert opened.status == "pitch_listo"


def test_settings_kv_pisa_video_enabled(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEO_ENABLED", "true")
    reset_settings()
    SettingsRepository(session).put("video_enabled", False, updated_by="test")
    lead = LeadRepository(session).add(make_lead(status="landing"))
    transition(session, lead, "pitch_listo", actor="sistema", reason="kv apaga el video")
    assert lead.status == "pitch_listo"

    monkeypatch.setenv("VIDEO_ENABLED", "false")
    reset_settings()
    SettingsRepository(session).put("video_enabled", True, updated_by="test")
    other = LeadRepository(session).add(make_lead(status="landing", business="Con video"))
    with pytest.raises(TransitionError):
        transition(session, other, "pitch_listo", actor="sistema", reason="kv enciende el video")
    assert other.status == "landing"


def test_perdido_solo_lo_reabre_un_humano_y_sin_supresion(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead(status="enviado", contact_email="hola@negocio.cl"))
    transition(session, lead, "perdido", actor="sistema", reason="secuencia agotada")
    assert lead.status == "perdido"
    assert lead.close_reason == "secuencia agotada"
    with pytest.raises(TransitionError):
        transition(session, lead, "nuevo", actor="agente", reason="reabrir")
    assert lead.status == "perdido"
    transition(session, lead, "nuevo", actor="humano", reason="el dueño lo reabre")
    assert lead.status == "nuevo"

    blocked = LeadRepository(session).add(
        make_lead(status="perdido", contact_email="baja@negocio.cl", business="Suprimido")
    )
    SuppressionRepository(session).add("email", "Baja@Negocio.cl", reason="opt-out", source="test")
    with pytest.raises(TransitionError):
        transition(session, blocked, "nuevo", actor="humano", reason="reabrir")
    assert blocked.status == "perdido"


def test_camino_feliz_hasta_postventa(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead())
    steps = [
        "diagnosticado",
        "landing",
        "video",
        "pitch_listo",
        "enviado",
        "respondio",
        "propuesta",
        "pagado",
        "en_produccion",
        "en_revision_cliente",
        "entregado",
        "postventa",
    ]
    for target in steps:
        transition(
            session,
            lead,
            target,
            actor="agente",
            reason=f"avanza a {target}",
            checker_approved=True,
        )
        assert lead.status == target
    with pytest.raises(TransitionError):
        transition(session, lead, "revision", actor="humano", reason="tarde")
    assert lead.status == "postventa"


def test_pagado_no_cae_a_perdido(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead(status="pagado"))
    with pytest.raises(TransitionError):
        transition(session, lead, "perdido", actor="humano", reason="arrepentido")
    assert lead.status == "pagado"
    transition(session, lead, "en_produccion", actor="sistema", reason="proyecto")
    assert lead.status == "en_produccion"


def test_motivo_vacio_y_actor_invalido(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead())
    with pytest.raises(TransitionError):
        transition(session, lead, "diagnosticado", actor="robot", reason="x")
    with pytest.raises(TransitionError):
        transition(session, lead, "diagnosticado", actor="agente", reason="   ")
    assert lead.status == "nuevo"


def test_tasa_de_respuesta_y_pausa_por_canal(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HITL_MIN_SAMPLE", "30")
    monkeypatch.setenv("HITL_RESPONSE_RATE", "0.12")
    reset_settings()
    assert response_rate(0, 0) == 0.0
    assert channel_should_pause("email_outreach", 29, 0) is False
    assert channel_should_pause("email_outreach", 30, 0) is True
    assert channel_should_pause("email_outreach", 30, 30) is False
    with pytest.raises(ValueError):
        response_rate(-1, 0)

    SettingsRepository(session).put(
        "hitl_response_rate_by_channel",
        {"email_outreach": 0.01},
        updated_by="test",
    )
    assert channel_should_pause("email_outreach", 30, 3, session=session) is False
    assert channel_should_pause("instagram", 30, 3, session=session) is True
