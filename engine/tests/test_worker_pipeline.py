"""El worker usa los agentes reales: artefactos en disco, aprobación y saldo."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from agents.builder import BuilderAgent
from agents.checker import CheckerAgent
from agents.closer import CloserAgent
from agents.delivery import DeliveryAgent
from agents.diagnoser import DiagnoserAgent
from agents.filmer import FilmerAgent
from agents.mobile import MobileAgent
from agents.pipeline import CycleResult, Orchestrator
from agents.pitcher import PitcherAgent
from agents.reporter import ReporterAgent
from api.deps import PaymentFact
from api.services import apply_payment, approve_project_public, load_demo
from core.config import reset_settings
from core.states import transition
from db.models import Approval, Artifact, Lead, LlmCall, Message, Order, Project
from db.repositories import LeadRepository
from db.session import create_all, reset_engine, session_scope
from worker import funnel
from worker.clock import FakeClock
from worker.funnel import job_pipeline
from worker.jobs import JOBS
from worker.ports import JobContext
from worker.runner import execute
from worker.testing_ports import build_default_ports

TZ = ZoneInfo("America/Santiago")
_OPEN = datetime(2026, 3, 3, 10, 0, tzinfo=TZ)


@pytest.fixture(autouse=True)
def _caches() -> object:
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
    monkeypatch.setenv("CLIENT_SITES_DIR", str(tmp_path / "sites"))
    monkeypatch.setenv("AGENCY_NAME", "Agencia Andina")
    monkeypatch.setenv("AGENCY_EMAIL", "hola@agencia-andina.example")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost")
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setenv("VIDEO_ENABLED", "true")
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "3")
    reset_settings()
    reset_engine()
    create_all()
    return tmp_path


@pytest.fixture
def session(env: Path) -> object:
    del env
    with session_scope() as current:
        yield current


def _ctx(session: Session) -> JobContext:
    return JobContext(
        session=session,
        clock=FakeClock(_OPEN),
        rng=random.Random(42),
        ports=build_default_ports(),
        allow_send=False,
    )


def _lead(session: Session, **overrides: object) -> Lead:
    data: dict[str, object] = {
        "source": "outbound_demo",
        "business": "Café Andes",
        "category": "cafeteria",
        "city": "Santiago",
        "commune": "Providencia",
        "opportunity_score": 80,
        "status": "nuevo",
        "estimated_value_clp": 350_000,
        "high_value": False,
        "tone": "tu",
        "contact_email": "cafe@andes-ejemplo.cl",
        "contact_email_source_url": "http://localhost/contacto",
    }
    data.update(overrides)
    return LeadRepository(session).add(Lead(**data))


def _order(session: Session, lead: Lead, **overrides: object) -> Order:
    data: dict[str, object] = {
        "lead_id": lead.id,
        "package_code": "landing_pro",
        "amount_clp": 168_067,
        "iva_clp": 31_933,
        "total_clp": 200_000,
        "deposit_percent": 50,
        "status": "pending",
    }
    data.update(overrides)
    order = Order(**data)
    session.add(order)
    session.flush()
    return order


def test_worker_y_demo_usan_los_mismos_agentes(
    session: Session,
    block_network: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del block_network
    assert funnel.DiagnoserAgent is DiagnoserAgent
    assert funnel.BuilderAgent is BuilderAgent
    assert funnel.FilmerAgent is FilmerAgent
    assert funnel.CheckerAgent is CheckerAgent
    assert funnel.PitcherAgent is PitcherAgent
    assert funnel.CloserAgent is CloserAgent
    assert funnel.DeliveryAgent is DeliveryAgent
    assert funnel.MobileAgent is MobileAgent
    assert funnel.ReporterAgent is ReporterAgent
    seen: list[str] = []

    def wrap(cls: type) -> None:
        original = cls.run

        def run(self: object, ctx: object) -> object:
            seen.append(cls.__name__)
            return original(self, ctx)

        monkeypatch.setattr(cls, "run", run)

    for cls in (
        DiagnoserAgent,
        BuilderAgent,
        FilmerAgent,
        CheckerAgent,
        PitcherAgent,
        CloserAgent,
        DeliveryAgent,
        MobileAgent,
        ReporterAgent,
    ):
        wrap(cls)
    _lead(session)
    assert execute("pipeline_tick", JOBS["pipeline_tick"], _ctx(session)) >= 1
    for name in (
        "DiagnoserAgent",
        "BuilderAgent",
        "FilmerAgent",
        "CheckerAgent",
        "PitcherAgent",
        "MobileAgent",
        "ReporterAgent",
    ):
        assert name in seen
    other = _lead(session, business="Otro Local", contact_email="otro@local-ejemplo.cl")
    monkeypatch.setattr("agents.pipeline.prepare_db", lambda: None)
    Orchestrator()._advance(session, other.id, CycleResult())
    assert seen.count("DiagnoserAgent") >= 2
    source = Path(funnel.__file__).read_text(encoding="utf-8")
    assert "_charge_llm" not in source
    assert "_diagnose" not in source
    assert "_ensure_artifact" not in source
    assert "Diagnóstico de" not in source
    stored = LeadRepository(session).get(other.id)
    assert stored is not None
    diagnosis = stored.diagnosis if isinstance(stored.diagnosis, dict) else {}
    markdown = str(diagnosis.get("markdown") or "")
    assert "Diagnóstico de" not in markdown
    assert stored.business in markdown


def test_artifacts_path_existe(session: Session, env: Path, block_network: None) -> None:
    del block_network
    lead = _lead(session, business="Panadería Sur")
    assert job_pipeline(_ctx(session)) >= 1
    rows = list(session.scalars(select(Artifact).where(Artifact.lead_id == lead.id)).all())
    assert rows
    for row in rows:
        assert Path(row.path).is_file(), row.path
        assert str(env / "out") in str(Path(row.path).resolve()) or Path(row.path).is_file()
    demo = next(row for row in rows if row.kind == "landing_demo")
    status, body, is_html = load_demo(session, demo.public_token)
    assert status == 200
    assert is_html is True
    assert isinstance(body, str)
    assert "Panadería Sur" in body
    story = [row for row in rows if row.kind == "storyboard"]
    assert story
    assert Path(story[0].path).read_text(encoding="utf-8")
    stored = LeadRepository(session).get(lead.id)
    assert stored is not None
    diagnosis = stored.diagnosis if isinstance(stored.diagnosis, dict) else {}
    assert diagnosis.get("pitch_body")
    assert "pitch_source" not in diagnosis
    messages = list(session.scalars(select(Message).where(Message.lead_id == lead.id)).all())
    outbound = [row for row in messages if row.direction == "out" and row.sequence_step == 1]
    assert outbound
    assert "Panadería Sur" in outbound[0].body_text
    assert "Te escribo de" not in outbound[0].body_text
    assert not any(
        row.tokens_in == 120 and row.cost_usd == Decimal("0.001")
        for row in session.scalars(select(LlmCall)).all()
    )


def test_pitch_sin_llm_usa_copywriter(session: Session, block_network: None) -> None:
    del block_network
    lead = _lead(session, status="pitch_listo", diagnosis={})
    job_pipeline(_ctx(session))
    stored = LeadRepository(session).get(lead.id)
    assert stored is not None
    diagnosis = stored.diagnosis if isinstance(stored.diagnosis, dict) else {}
    assert diagnosis.get("pitch_source") == "copywriter"
    message = session.scalar(select(Message).where(Message.lead_id == lead.id))
    assert message is not None
    assert "Te escribo de" in message.body_text
    assert message.channel == "email_outreach"


def test_presupuesto_real_no_fabrica_llm(session: Session, block_network: None) -> None:
    del block_network
    moment = _OPEN.astimezone(UTC)
    lead = _lead(session, business="Sin Cupo")
    session.add(
        LlmCall(
            agent="diagnoser",
            model="grok-4.7",
            prompt_name="diagnoser",
            prompt_version="1",
            tokens_in=10,
            tokens_out=10,
            cost_usd=Decimal("3"),
            latency_ms=1,
            ok=True,
            lead_id=lead.id,
            ts=moment,
        )
    )
    session.flush()
    assert job_pipeline(_ctx(session)) == 0
    stored = LeadRepository(session).get(lead.id)
    assert stored is not None
    assert stored.status == "nuevo"
    assert stored.diagnosis is None
    calls = list(session.scalars(select(LlmCall)).all())
    assert len(calls) == 1
    assert calls[0].tokens_in == 10


def test_entrega_requiere_aprobacion_del_cliente(
    session: Session,
    env: Path,
    block_network: None,
) -> None:
    del block_network
    waiting = _lead(session, business="Espera Cliente", status="en_revision_cliente")
    produced = _lead(session, business="Obra Lista", status="en_produccion")
    order = _order(session, produced, status="deposit_paid")
    session.add(
        Project(
            order_id=order.id,
            lead_id=produced.id,
            status="en_produccion",
            revisions_used=0,
            max_revisions=2,
            intake={"objetivo": "Mostrar el horario propio"},
        )
    )
    session.flush()
    ctx = _ctx(session)
    job_pipeline(ctx)
    job_pipeline(ctx)
    assert LeadRepository(session).get(waiting.id).status == "en_revision_cliente"  # type: ignore[union-attr]
    stored = LeadRepository(session).get(produced.id)
    assert stored is not None
    assert stored.status == "en_revision_cliente"
    assert stored.status != "entregado"
    rows = list(session.scalars(select(Artifact).where(Artifact.lead_id == produced.id)).all())
    assert len(rows) == 1
    html = Path(rows[0].path).read_text(encoding="utf-8")
    assert "Mostrar el horario propio" in html
    assert "Obra Lista" in html
    assert Path(rows[0].path).is_file()
    preview = list((env / "sites").rglob("index.html"))
    assert any("Mostrar el horario propio" in page.read_text(encoding="utf-8") for page in preview)
    assert not list(session.scalars(select(Project).where(Project.status == "publicado")).all())


def test_publica_solo_con_saldo_pagado(
    session: Session,
    env: Path,
    block_network: None,
) -> None:
    del block_network
    lead = _lead(
        session,
        business="Cafe Saldo",
        status="propuesta",
        contact_email="caja@saldo-ejemplo.cl",
    )
    order = _order(session, lead)
    first = apply_payment(
        session,
        PaymentFact(
            provider_payment_id="pay-anticipo",
            status="approved",
            amount_clp=100_000,
            order_id=order.id,
            lead_id=lead.id,
        ),
    )
    assert first["duplicate"] is False
    session.refresh(order)
    session.refresh(lead)
    assert order.status == "deposit_paid"
    assert lead.status == "pagado"
    project = session.scalar(select(Project).where(Project.lead_id == lead.id))
    assert project is not None
    assert project.status != "publicado"
    transition(session, lead, "en_produccion", actor="sistema", reason="intake de prueba")
    transition(session, lead, "en_revision_cliente", actor="sistema", reason="preview de prueba")
    session.execute(
        update(Project).where(Project.id == project.id).values(status="en_revision_cliente")
    )
    session.flush()
    held = approve_project_public(session, project.portal_token)
    assert held["status"] == "saldo_pendiente"
    session.refresh(lead)
    session.refresh(order)
    session.refresh(project)
    assert lead.status == "en_revision_cliente"
    assert project.status != "publicado"
    assert order.provider_preference_id is not None
    assert order.provider_preference_id.startswith("fake-pref-")
    intake = project.intake if isinstance(project.intake, dict) else {}
    assert intake.get("balance_due_clp") == 100_000
    assert intake.get("client_approved") is True
    early = [path for path in (env / "sites").rglob("index.html") if "_previews" not in path.parts]
    assert early == []
    paid = apply_payment(
        session,
        PaymentFact(
            provider_payment_id="pay-saldo",
            status="approved",
            amount_clp=100_000,
            order_id=order.id,
            lead_id=lead.id,
        ),
    )
    assert paid["duplicate"] is False
    session.expire_all()
    done = session.get(Lead, lead.id)
    published = session.get(Project, project.id)
    closed = session.get(Order, order.id)
    assert done is not None and done.status == "entregado"
    assert published is not None and published.status == "publicado"
    assert closed is not None and closed.status == "paid"
    assert published.deploy_url
    deploy = Path(published.deploy_url)
    page = deploy / "index.html"
    assert page.is_file()
    assert "Cafe Saldo" in page.read_text(encoding="utf-8")
    mail = session.scalar(
        select(Message).where(Message.lead_id == lead.id, Message.channel == "email_tx")
    )
    assert mail is not None
    assert mail.status == "sent"
    assert "Cafe Saldo" in mail.body_text
    assert published.deploy_url in mail.body_text


def test_monto_pagado_distinto_crea_approval(session: Session, block_network: None) -> None:
    del block_network
    lead = _lead(session, business="Monto Raro", status="propuesta")
    order = _order(session, lead)
    result = apply_payment(
        session,
        PaymentFact(
            provider_payment_id="pay-mal",
            status="approved",
            amount_clp=10,
            order_id=order.id,
            lead_id=lead.id,
        ),
    )
    assert result["duplicate"] is False
    session.refresh(order)
    session.refresh(lead)
    assert order.status == "pending"
    assert lead.status == "propuesta"
    assert session.scalar(select(Project).where(Project.order_id == order.id)) is None
    rows = list(
        session.scalars(
            select(Approval).where(Approval.lead_id == lead.id, Approval.kind == "compliance")
        ).all()
    )
    assert len(rows) == 1
    payload = rows[0].payload if isinstance(rows[0].payload, dict) else {}
    assert payload.get("amount_clp") == 10
    assert 100_000 in payload.get("expected_clp", [])
    assert 200_000 in payload.get("expected_clp", [])
