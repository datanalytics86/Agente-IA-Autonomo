"""Cuotas, opt-out, canales manuales, alto valor y reintentos."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.compliance import check_rules
from core.config import reset_settings
from db.models import Approval, Artifact, Lead, Message, Project
from db.repositories import LeadRepository, MessageRepository, SettingsRepository
from db.session import create_all, reset_engine, session_scope
from worker.clock import FakeClock
from worker.copywriter import checker_settings, outreach_parts
from worker.defaults import GuardedOutreach, build_default_ports
from worker.jobs import JOBS
from worker.maintenance import job_demo_expiry, job_postventa, job_retention
from worker.ports import InboundMail, JobContext, SendResult
from worker.runner import execute
from worker.sending import apply_inbound, job_outreach, job_warmup

TZ = ZoneInfo("America/Santiago")


class MemoryOutreach:
    def __init__(self, outcome: str = "sent") -> None:
        self.outcome = outcome
        self.sent: list[str] = []

    def send(
        self,
        message_id: str,
        to: str,
        subject: str,
        text: str,
        html: str,
    ) -> SendResult:
        self.sent.append(to)
        return SendResult(status=self.outcome, provider_message_id=f"m-{message_id}")


@pytest.fixture(autouse=True)
def _caches() -> object:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> object:
    url = f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_settings()
    reset_engine()
    create_all()
    with session_scope() as current:
        yield current


def _lead(session: Session, **overrides: object) -> Lead:
    data: dict[str, object] = {
        "source": "outbound_demo",
        "business": "Café Andes",
        "category": "cafeteria",
        "city": "Santiago",
        "commune": "Providencia",
        "opportunity_score": 80,
        "status": "pitch_listo",
        "estimated_value_clp": 350_000,
        "high_value": False,
        "tone": "tu",
        "contact_email": "cafe@andes-ejemplo.cl",
    }
    data.update(overrides)
    return LeadRepository(session).add(Lead(**data))


def _queued(session: Session, lead: Lead, **overrides: object) -> Message:
    subject, text, body = outreach_parts(
        business=lead.business,
        commune=lead.commune,
        step=1,
    )
    result = check_rules(
        {
            "body": text,
            "body_html": body,
            "channel": "email_outreach",
            "direction": "out",
            "subject": subject,
            "suppressed": False,
            "recipient_suppressed": False,
        },
        {"contact_email": lead.contact_email, "business": lead.business},
        checker_settings(),
    )
    assert result.approved, result.reasons
    data: dict[str, object] = {
        "lead_id": lead.id,
        "thread_id": lead.id,
        "direction": "out",
        "channel": "email_outreach",
        "sequence_step": 1,
        "status": "queued",
        "subject": subject,
        "body_text": text,
        "body_html": body,
        "check_result": {"approved": True, "rules": result.model_dump()},
        "scheduled_at": datetime(2026, 3, 3, 13, 0, tzinfo=UTC),
    }
    data.update(overrides)
    return MessageRepository(session).add(Message(**data))


def _ctx(session: Session, moment: datetime, outreach: object | None = None) -> JobContext:
    ports = build_default_ports()
    if outreach is not None:
        ports.outreach = outreach  # type: ignore[assignment]
    return JobContext(
        session=session,
        clock=FakeClock(moment),
        rng=random.Random(42),
        ports=ports,
        allow_send=True,
    )


def test_borrador_pasa_el_checker() -> None:
    subject, text, body = outreach_parts(business="Café Andes", commune="Ñuñoa", step=2)
    result = check_rules(
        {
            "body": text,
            "body_html": body,
            "channel": "email_outreach",
            "subject": subject,
            "direction": "out",
        },
        {"business": "Café Andes"},
        checker_settings(),
    )
    assert result.approved, result.reasons


def test_kill_switch_no_envia(session: Session) -> None:
    lead = _lead(session)
    _queued(session, lead)
    ctx = _ctx(session, datetime(2026, 3, 3, 14, 0, tzinfo=TZ), MemoryOutreach())
    ctx.allow_send = False
    assert job_outreach(ctx) == 0
    assert ctx.ports.outreach.sent == []  # type: ignore[attr-defined]
    stored = MessageRepository(session).list(lead_id=lead.id)[0]
    assert stored.status == "queued"


def test_envio_dentro_de_ventana_marca_enviado(session: Session) -> None:
    SettingsRepository(session).put("kill_switch", True, updated_by="test")
    lead = _lead(session)
    _queued(session, lead)
    box = MemoryOutreach()
    ctx = _ctx(session, datetime(2026, 3, 3, 10, 0, tzinfo=TZ), box)
    assert execute("outreach_send", JOBS["outreach_send"], ctx) == 1
    assert box.sent == ["cafe@andes-ejemplo.cl"]
    stored = MessageRepository(session).list(lead_id=lead.id)[0]
    assert stored.status == "sent"
    assert LeadRepository(session).get(lead.id).status == "enviado"  # type: ignore[union-attr]


def test_fuera_de_ventana_no_envia(session: Session) -> None:
    lead = _lead(session)
    _queued(session, lead)
    box = MemoryOutreach()
    ctx = _ctx(session, datetime(2026, 3, 3, 14, 30, tzinfo=TZ), box)
    assert job_outreach(ctx) == 0
    assert box.sent == []


def test_feriado_no_envia(session: Session) -> None:
    lead = _lead(session)
    _queued(session, lead)
    box = MemoryOutreach()
    ctx = _ctx(session, datetime(2026, 9, 18, 10, 0, tzinfo=TZ), box)
    assert job_outreach(ctx) == 0
    assert box.sent == []


def test_cupo_diario_y_por_dominio(session: Session) -> None:
    SettingsRepository(session).put(
        "quotas",
        {"email_outreach_daily_limit": 2},
        updated_by="test",
    )
    first = _lead(session, business="Uno", contact_email="a@uno-ejemplo.cl")
    second = _lead(session, business="Dos", commune="Ñuñoa", contact_email="b@dos-ejemplo.cl")
    same = _lead(session, business="Tres", commune="Maipú", contact_email="c@uno-ejemplo.cl")
    extra = _lead(
        session,
        business="Cuatro",
        commune="La Florida",
        contact_email="d@tres-ejemplo.cl",
    )
    _queued(session, first, scheduled_at=datetime(2026, 3, 3, 12, 0, tzinfo=UTC))
    _queued(session, same, scheduled_at=datetime(2026, 3, 3, 12, 5, tzinfo=UTC))
    _queued(session, second, scheduled_at=datetime(2026, 3, 3, 12, 10, tzinfo=UTC))
    _queued(session, extra, scheduled_at=datetime(2026, 3, 3, 12, 15, tzinfo=UTC))
    box = MemoryOutreach()
    moment = datetime(2026, 3, 3, 10, 0, tzinfo=TZ)
    ctx = _ctx(session, moment, box)
    assert job_outreach(ctx) == 1
    ctx.clock.advance_to(moment + timedelta(minutes=8))  # type: ignore[attr-defined]
    assert job_outreach(ctx) == 1
    ctx.clock.advance_to(moment + timedelta(minutes=16))  # type: ignore[attr-defined]
    assert job_outreach(ctx) == 0
    assert box.sent == ["a@uno-ejemplo.cl", "b@dos-ejemplo.cl"]
    same_rows = MessageRepository(session).list(lead_id=same.id)
    extra_rows = MessageRepository(session).list(lead_id=extra.id)
    assert [row.status for row in same_rows] == ["queued"]
    assert [row.status for row in extra_rows] == ["queued"]


def test_canales_manuales_no_pasan_a_sent(session: Session) -> None:
    lead = _lead(session, contact_email=None, instagram_handle="cafe")
    for channel in ("instagram", "linkedin", "whatsapp"):
        MessageRepository(session).add(
            Message(
                lead_id=lead.id,
                thread_id=lead.id,
                direction="out",
                channel=channel,
                sequence_step=1,
                status="queued",
                body_text="borrador",
                scheduled_at=datetime(2026, 3, 3, 13, 0, tzinfo=UTC),
            )
        )
    box = MemoryOutreach()
    ctx = _ctx(session, datetime(2026, 3, 3, 10, 0, tzinfo=TZ), box)
    job_outreach(ctx)
    assert box.sent == []
    for message in MessageRepository(session).list(lead_id=lead.id):
        assert message.status == "manual_pending"


def test_alto_valor_va_a_revision_sin_envio(session: Session) -> None:
    lead = _lead(session, estimated_value_clp=2_800_000, high_value=True, business="Clínica")
    _queued(session, lead)
    box = MemoryOutreach()
    ctx = _ctx(session, datetime(2026, 3, 3, 10, 0, tzinfo=TZ), box)
    assert job_outreach(ctx) == 0
    assert box.sent == []
    stored = LeadRepository(session).get(lead.id)
    assert stored is not None
    assert stored.status == "revision"
    kinds = [row.kind for row in session.scalars(select(Approval)).all()]
    assert "deal_alto_valor" in kinds


def test_opt_out_en_el_mismo_tick(session: Session) -> None:
    lead = _lead(session, status="enviado", business="Opt")
    MessageRepository(session).add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="out",
            channel="email_outreach",
            sequence_step=2,
            status="queued",
            body_text="seguimiento",
            check_result={"approved": True},
            scheduled_at=datetime(2026, 3, 3, 13, 0, tzinfo=UTC),
        )
    )
    box = MemoryOutreach()
    ctx = _ctx(session, datetime(2026, 3, 3, 10, 0, tzinfo=TZ), box)
    apply_inbound(
        ctx,
        [InboundMail(from_email="cafe@andes-ejemplo.cl", body="Por favor BAJA", intent="otro")],
    )
    job_outreach(ctx)
    stored = LeadRepository(session).get(lead.id)
    assert stored is not None
    assert stored.status == "opt_out"
    assert box.sent == []
    follow = [
        row
        for row in MessageRepository(session).list(lead_id=lead.id)
        if row.direction == "out"
    ]
    assert len(follow) == 1
    assert follow[0].status == "blocked"


def test_warmup_sube_cinco_los_lunes(session: Session) -> None:
    ctx = _ctx(session, datetime(2026, 3, 2, 7, 0, tzinfo=TZ))
    assert job_warmup(ctx) == 1
    assert job_warmup(ctx) == 0
    quotas = SettingsRepository(session).get("quotas")
    assert quotas["email_outreach_daily_limit"] == 20
    tuesday = _ctx(session, datetime(2026, 3, 3, 7, 0, tzinfo=TZ))
    assert job_warmup(tuesday) == 0
    assert SettingsRepository(session).get("quotas")["email_outreach_daily_limit"] == 20


def test_tres_fallos_crean_error_sistema(session: Session) -> None:
    ctx = _ctx(session, datetime(2026, 3, 3, 10, 0, tzinfo=TZ))

    def boom(_ctx: JobContext) -> int:
        raise RuntimeError("fallo de prueba")

    assert execute("scout", boom, ctx) == 0
    rows = list(session.scalars(select(Approval).where(Approval.kind == "error_sistema")).all())
    assert len(rows) == 1
    assert rows[0].payload["job"] == "scout"


def test_retencion_demo_y_postventa(session: Session) -> None:
    old = _lead(
        session,
        status="nuevo",
        business="Viejo",
        contact_email="viejo@ejemplo.cl",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    ctx = _ctx(session, datetime(2026, 3, 3, 3, 30, tzinfo=TZ))
    assert job_retention(ctx) == 1
    assert LeadRepository(session).get(old.id).anonymized_at is not None  # type: ignore[union-attr]

    artifact = Artifact(
        lead_id=old.id,
        kind="landing_demo",
        path="output/demo/x.html",
        expires_at=datetime(2026, 3, 1, tzinfo=UTC),
        meta={},
    )
    session.add(artifact)
    session.flush()
    assert job_demo_expiry(ctx) == 1
    assert artifact.meta["expired"] is True

    delivered = _lead(session, status="entregado", business="Listo", commune="Ñuñoa")
    session.add(
        Project(
            order_id=_order(session, delivered),
            lead_id=delivered.id,
            status="aprobado",
            max_revisions=1,
            delivered_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.flush()
    assert job_postventa(ctx) == 1
    assert LeadRepository(session).get(delivered.id).status == "postventa"  # type: ignore[union-attr]


def _order(session: Session, lead: Lead) -> str:
    from db.models import Order
    from db.repositories import OrderRepository

    order = OrderRepository(session).add(
        Order(
            lead_id=lead.id,
            package_code="landing_pro",
            amount_clp=100,
            iva_clp=19,
            total_clp=119,
            deposit_percent=50,
            status="paid",
        )
    )
    return order.id


def test_guarded_outreach_no_declara_envio() -> None:
    result = GuardedOutreach().send("1", "a@b.cl", "s", "t", "<p>t</p>")
    assert result.status == "blocked"
