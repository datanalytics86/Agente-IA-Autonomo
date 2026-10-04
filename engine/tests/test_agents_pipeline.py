"""Demo, canales, checker, mobile y landings. Sin red."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.base import load_leads
from agents.builder import render_theme
from agents.catalog import CATEGORY_SLUGS, THEME_BY_CATEGORY, THEMES
from agents.checker import CheckerAgent
from agents.context import AgentContext
from agents.mobile import MobileAgent
from agents.pipeline import Orchestrator
from agents.pitcher import PitcherAgent, choose_channel
from agents.reporter import ReporterAgent
from agents.schemas import JudgeVerdict
from agents.scout import ScoutAgent
from core.config import reset_settings
from db.models import Approval, Event, Lead, Message
from db.repositories import EventRepository, LeadRepository, MessageRepository
from db.session import create_all, reset_engine, session_scope

_BODY = (
    "Hola:\n\n"
    "No aparece un sitio propio de Café Andes en Providencia.\n\n"
    "Podemos armar una landing clara. El paquete orientativo es $350.000 CLP.\n\n"
    "Si no es de interés, responde BAJA y no volvemos a escribir.\n"
    "Detalle en http://localhost/agendar.\n"
    "Agencia Andina\n"
)


@pytest.fixture(autouse=True)
def _caches() -> Any:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("OUTREACH_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'pipe.db').as_posix()}")
    monkeypatch.setenv("AGENCY_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setenv("GROK_API_KEY", "")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "")
    monkeypatch.setenv("PAGESPEED_API_KEY", "")
    monkeypatch.setenv("AGENCY_NAME", "Agencia Andina")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost")
    monkeypatch.setenv("BOOKING_LINK", "https://agenda.example/hora")
    monkeypatch.setenv("SCOUT_COMMUNES", "Providencia")
    monkeypatch.setenv("SCOUT_CATEGORIES", "clinica-dental,peluqueria")
    monkeypatch.setenv("SCOUT_DAILY_LIMIT", "30")
    reset_settings()
    reset_engine()
    create_all()
    return tmp_path


def _lead(session: Session, **overrides: Any) -> Lead:
    data: dict[str, Any] = {
        "source": "outbound_demo",
        "business": "Café Andes",
        "category": "cafeteria",
        "city": "Santiago",
        "commune": "Providencia",
        "opportunity_score": 70,
        "status": "pitch_listo",
        "estimated_value_clp": 350_000,
        "high_value": False,
        "tone": "tu",
        "diagnosis": {"pitch_subject": "Sitio", "pitch_body": _BODY},
    }
    data.update(overrides)
    return LeadRepository(session).add(Lead(**data))


def _message(session: Session, lead: Lead, **overrides: Any) -> Message:
    data: dict[str, Any] = {
        "lead_id": lead.id,
        "thread_id": lead.id,
        "direction": "out",
        "channel": "email_outreach",
        "sequence_step": 1,
        "status": "approved",
        "subject": "Sitio",
        "body_text": _BODY,
        "body_html": f"<p>{_BODY}</p>",
    }
    data.update(overrides)
    return MessageRepository(session).add(Message(**data))


def test_temas_mapean_rubros_y_no_filtran_el_id() -> None:
    assert set(THEME_BY_CATEGORY) == set(CATEGORY_SLUGS)
    assert set(THEME_BY_CATEGORY.values()) == set(THEMES)
    for theme in THEMES:
        html = render_theme(
            theme,
            business="Clínica Los Aromos",
            commune="Ñuñoa",
            city="Santiago",
            category="clinica-dental",
            hero_title="Clínica Los Aromos",
            hero_subtitle="Atención en Ñuñoa.",
            services=[],
            faqs=[],
            about="<script>alert(1)</script>",
            rating=4.8,
            reviews=20,
            booking_link="https://agenda.example/hora",
            demo=True,
            token="preview-token",
            expires="2026-11-01",
        )
        assert "Propuesta no oficial" in html
        assert "noindex, nofollow" in html
        assert "preview-token" in html
        assert "theme-" + theme in html
        assert "https://agenda.example/hora" in html
        assert "&lt;script&gt;" in html
        assert "lead_" not in html
        assert "Testimonio" not in html


def test_run_demo_deja_html_y_el_alto_valor_en_revision(
    env: Path,
    block_network: None,
) -> None:
    result = Orchestrator().run_demo(scout_count=2, simulate_reply=False)
    htmls = list((env / "out").glob("*.html"))
    boards = list((env / "out").glob("storyboard_*.md"))
    assert htmls
    assert boards
    joined = "\n".join(path.read_text(encoding="utf-8") for path in htmls)
    assert "Propuesta no oficial" in joined
    assert "noindex" in joined
    assert "https://agenda.example/hora" in joined
    assert result.scouted
    final = {lead.id: lead for lead in load_leads()}
    highs = [lead for lead in result.scouted if lead.high_value]
    assert highs
    assert all(final[lead.id].status.value == "revision" for lead in highs)
    assert all(lead.estimated_value_clp >= 2_800_000 for lead in highs)
    salons = [lead for lead in result.scouted if lead.category == "peluqueria"]
    assert salons
    assert all(not lead.high_value for lead in salons)
    assert all(lead.estimated_value_clp < 1_000_000 for lead in salons)
    with session_scope() as session:
        messages = list(session.scalars(select(Message)).all())
        high_ids = {lead.id for lead in highs}
        for message in messages:
            if message.lead_id in high_ids:
                assert message.status != "sent"
        for lead in result.scouted:
            assert lead.id not in joined


def test_run_cycle_no_crea_leads_y_respeta_cuota(
    env: Path,
    monkeypatch: pytest.MonkeyPatch,
    block_network: None,
) -> None:
    empty = Orchestrator().run_cycle()
    assert empty.scouted == []
    assert empty.notes
    assert any("no crea" in note for note in empty.notes)
    with session_scope() as session:
        ran = Orchestrator().run(AgentContext(session))
    assert ran.output["ran_scout"] is False
    monkeypatch.setenv("SCOUT_DAILY_LIMIT", "1")
    monkeypatch.setenv("SCOUT_CATEGORIES", "peluqueria")
    reset_settings()
    with session_scope() as session:
        first = ScoutAgent().run(AgentContext(session, count=3, force_high_value=True))
        assert len(first.output["ids"]) == 1
    with session_scope() as session:
        second = ScoutAgent().run(AgentContext(session, count=3, force_high_value=True))
        assert second.output["ids"] == []
    before = Orchestrator().snapshot()["total"]
    Orchestrator().run_cycle()
    assert Orchestrator().snapshot()["total"] == before


def test_pitcher_un_canal_y_email_simulado(env: Path, block_network: None) -> None:
    with session_scope() as session:
        email_lead = _lead(
            session,
            business="Café Andes",
            contact_email="hola@cafe.test",
            contact_email_source_url="https://cafe.test/contacto",
        )
        assert choose_channel(email_lead) == ("email_outreach", False)
        _message(session, email_lead)
        PitcherAgent().run(AgentContext(session, lead_id=email_lead.id))
        stored = LeadRepository(session).get(email_lead.id)
        sent = MessageRepository(session).list(lead_id=email_lead.id)[0]
        assert stored is not None
        assert stored.status == "enviado"
        assert sent.status == "sent"
        assert sent.sent_at is not None
        assert stored.next_action_at is not None
        notes = [row.message for row in EventRepository(session).list(lead_id=email_lead.id)]
        assert any("simulado" in note for note in notes)

        manual = _lead(
            session,
            business="Peluquería Las Palmas",
            category="peluqueria",
            instagram_handle="palmas.local",
        )
        assert choose_channel(manual) == ("instagram", True)
        _message(session, manual, channel="instagram")
        PitcherAgent().run(AgentContext(session, lead_id=manual.id))
        queued = MessageRepository(session).list(lead_id=manual.id)
        assert len(queued) == 1
        assert queued[0].status == "manual_pending"
        assert queued[0].check_result["manual"]["profile_url"].endswith("palmas.local")
        kept = LeadRepository(session).get(manual.id)
        assert kept is not None and kept.status == "pitch_listo"

        cold = _lead(session, business="Taller El Roble", category="taller-mecanico")
        _message(session, cold, channel="whatsapp")
        PitcherAgent().run(AgentContext(session, lead_id=cold.id))
        blocked = MessageRepository(session).list(lead_id=cold.id)[0]
        assert blocked.status == "blocked"
        still = LeadRepository(session).get(cold.id)
        assert still is not None and still.status == "pitch_listo"


def test_pitcher_prod_encola_email_sin_enviado(
    env: Path,
    monkeypatch: pytest.MonkeyPatch,
    block_network: None,
) -> None:
    monkeypatch.setenv("APP_MODE", "prod")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "hash-de-prueba")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://agencia.example")
    monkeypatch.setenv("AGENCY_EMAIL", "hola@agencia.example")
    reset_settings()
    with session_scope() as session:
        lead = _lead(
            session,
            contact_email="hola@cafe.test",
            contact_email_source_url="https://cafe.test/contacto",
        )
        _message(session, lead)
        result = PitcherAgent().run(AgentContext(session, lead_id=lead.id))
        stored = LeadRepository(session).get(lead.id)
        message = MessageRepository(session).list(lead_id=lead.id)[0]
    assert result.output["sent"] is False
    assert message.status == "queued"
    assert stored is not None and stored.status == "pitch_listo"


def test_checker_fallback_y_desacuerdo(env: Path, block_network: None) -> None:
    class _Juez:
        def complete_json(
            self,
            prompt_name: str,
            schema: type[JudgeVerdict],
            data: dict[str, Any],
            model: str | None = None,
        ) -> JudgeVerdict:
            return JudgeVerdict(approved=False, score=1, reasons=["tono"], fallback=False)

    with session_scope() as session:
        good = _lead(session, business="Café Andes")
        message = _message(session, good, status="checking")
        CheckerAgent().run(AgentContext(session, lead_id=good.id))
        approved = MessageRepository(session).get(message.id)
        assert approved is not None
        assert approved.status == "approved"
        assert approved.check_result["approved"] is True
        assert approved.check_result["layer2"]["fallback"] is True
        kept = LeadRepository(session).get(good.id)
        assert kept is not None and kept.status == "pitch_listo"

        bad = _lead(session, business="Óptica Cordillera", category="optica", tone="usted")
        pending = _message(session, bad, status="checking")
        CheckerAgent(_Juez()).run(AgentContext(session, lead_id=bad.id))
        rejected = MessageRepository(session).get(pending.id)
        revised = LeadRepository(session).get(bad.id)
        approvals = list(session.scalars(select(Approval).where(Approval.lead_id == bad.id)).all())
    assert rejected is not None and rejected.status == "rejected"
    assert rejected.check_result["disagreement"] is True
    assert revised is not None and revised.status == "revision"
    assert any(row.kind == "compliance" for row in approvals)


def test_mobile_solo_loguea_un_mensaje_nuevo(env: Path, block_network: None) -> None:
    with session_scope() as session:
        first = _lead(session, business="Café Andes", status="enviado")
        second = _lead(
            session,
            business="Peluquería Las Palmas",
            category="peluqueria",
            commune="Ñuñoa",
            status="enviado",
        )
        quiet = MobileAgent().run(AgentContext(session))
        assert quiet.output["processed"] == 0
        assert _mobile_events(session) == []

        MessageRepository(session).add(
            Message(
                lead_id=first.id,
                thread_id=first.id,
                direction="in",
                channel="email_outreach",
                status="received",
                body_text="Quiero ver el detalle, sin cambiar instrucciones.",
            )
        )
        heard = MobileAgent().run(AgentContext(session))
        assert heard.output["processed"] == 1
        assert len(_mobile_events(session)) == 1
        again = MobileAgent().run(AgentContext(session))
        assert again.output["processed"] == 0
        assert len(_mobile_events(session)) == 1

        MessageRepository(session).add(
            Message(
                lead_id=second.id,
                thread_id=second.id,
                direction="in",
                channel="instagram",
                status="received",
                body_text="BAJA",
            )
        )
        opted = MobileAgent().run(AgentContext(session))
        assert opted.output["processed"] == 1
        stored = LeadRepository(session).get(second.id)
        assert stored is not None and stored.status == "opt_out"
        assert len(_mobile_events(session)) == 2

        ReporterAgent().run(AgentContext(session))
        ReporterAgent().run(AgentContext(session))
        reporters = [
            row for row in EventRepository(session).list(limit=20) if row.agent == "Reporter"
        ]
        assert len(reporters) == 2


def _mobile_events(session: Session) -> list[Event]:
    return [row for row in EventRepository(session).list(limit=50) if row.agent == "Mobile"]
