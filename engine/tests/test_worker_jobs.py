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
from db.models import Approval, Artifact, JobRun, Lead, LlmCall, Message, Project
from db.repositories import (
    LeadRepository,
    MessageRepository,
    SettingsRepository,
    SuppressionRepository,
)
from db.session import create_all, reset_engine, session_scope
from worker.clock import FakeClock
from worker.copywriter import agency_label, checker_settings, outreach_parts
from worker.defaults import EmptySource, GuardedOutreach, build_default_ports
from worker.funnel import _charge_llm, _ensure_artifact, job_pipeline, job_scout
from worker.jobs import JOBS
from worker.maintenance import job_demo_expiry, job_postventa, job_retention
from worker.ports import InboundMail, JobContext, PlaceHit, SendResult
from worker.runner import drain_queued, execute
from worker.sending import apply_inbound, job_followups, job_outreach, job_warmup

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
        *,
        lead_id: str = "",
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
    monkeypatch.setenv("AGENCY_NAME", "Agencia Andina")
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
    source = "https://andes-ejemplo.cl/contacto"
    subject, text, body = outreach_parts(
        business=lead.business,
        commune=lead.commune,
        step=1,
        source=source,
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
        {
            "contact_email": lead.contact_email,
            "business": lead.business,
            "contact_email_source_url": source,
        },
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


def test_html_conserva_los_saltos_del_pie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENCY_NAME", raising=False)
    reset_settings()
    _subject, text, body = outreach_parts(
        business="Café Andes",
        commune="Ñuñoa",
        step=1,
        source="https://cafe.cl/contacto",
    )
    assert "<br>" in body
    assert body.startswith("<p>") and body.endswith("</p>")
    for line in text.split("\n"):
        assert html_escape_line(line) in body


def html_escape_line(line: str) -> str:
    return line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def test_sin_nombre_usa_deeppro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENCY_NAME", raising=False)
    reset_settings()
    assert agency_label() == "DEEP PRO CONSULTORES SpA"
    _subject, text, body = outreach_parts(business="Café Andes", commune="Ñuñoa", step=1)
    assert "DEEP PRO CONSULTORES SpA" in text
    assert "DEEP PRO CONSULTORES SpA" in body


def test_borrador_pasa_el_checker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENCY_NAME", "Agencia Andina")
    reset_settings()
    source = "https://andes-ejemplo.cl/contacto"
    subject, text, body = outreach_parts(
        business="Café Andes",
        commune="Ñuñoa",
        step=2,
        source=source,
    )
    result = check_rules(
        {
            "body": text,
            "body_html": body,
            "channel": "email_outreach",
            "subject": subject,
            "direction": "out",
        },
        {"business": "Café Andes", "contact_email_source_url": source},
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


def test_email_suprimido_no_recibe_mas(session: Session) -> None:
    lead = _lead(session)
    SuppressionRepository(session).add(
        "email",
        lead.contact_email or "",
        reason="baja",
        source="baja",
    )
    _queued(session, lead)
    box = MemoryOutreach()
    ctx = _ctx(session, datetime(2026, 3, 3, 10, 0, tzinfo=TZ), box)
    assert job_outreach(ctx) == 0
    assert box.sent == []
    stored = MessageRepository(session).list(lead_id=lead.id)[0]
    assert stored.status == "blocked"


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
        row for row in MessageRepository(session).list(lead_id=lead.id) if row.direction == "out"
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


def test_no_inventa_costo_ni_archivo_ni_entrega(session: Session, tmp_path: Path) -> None:
    ctx = _ctx(session, datetime(2026, 3, 3, 12, 0, tzinfo=TZ))
    nuevo = _lead(session, status="nuevo", business="Nuevo Local")
    assert _charge_llm(ctx, nuevo.id, "diagnoser") is True
    assert list(session.scalars(select(LlmCall)).all()) == []
    produccion = _lead(session, status="en_produccion", business="En obra")
    revision = _lead(session, status="en_revision_cliente", business="En revision")
    JOBS["pipeline_tick"](ctx)
    assert LeadRepository(session).get(produccion.id).status == "en_produccion"  # type: ignore[union-attr]
    assert LeadRepository(session).get(revision.id).status == "en_revision_cliente"  # type: ignore[union-attr]
    _ensure_artifact(ctx, nuevo, "landing_demo", "output/no-existe.html")
    assert list(session.scalars(select(Artifact)).all()) == []
    real = tmp_path / "index.html"
    real.write_text("<p>ok</p>", encoding="utf-8")
    _ensure_artifact(ctx, nuevo, "landing_demo", str(real))
    rows = list(session.scalars(select(Artifact)).all())
    assert len(rows) == 1
    assert rows[0].path == str(real)


def _origen(**overrides: object) -> object:
    class Hit:
        place_id = "place-1"
        name = "Café Norte"
        formatted_address = "Av 1"
        commune = "Providencia"
        city = "Santiago"
        category = "cafeteria"
        website_uri = None
        rating = 4.8
        user_rating_count = 40
        business_status = "OPERATIONAL"
        email = "hola@negocio.cl"
        instagram_handle = None
        linkedin_url = None
        phone_public = None
        estimated_value_clp = 350_000
        opportunity_score = 80
        scenario = "test"
        unsafe_text = ""

    hit = Hit()
    for key, value in overrides.items():
        setattr(hit, key, value)
    return hit


def _mensaje_del_hit(session: Session, **overrides: object) -> tuple[Lead, Message]:
    from worker.defaults import place_from_source
    from worker.funnel import _lead_from_hit, _queue_messages

    mapped = place_from_source(_origen(**overrides), commune="Providencia", category="cafeteria")
    assert mapped is not None
    ctx = _ctx(session, datetime(2026, 3, 3, 12, 0, tzinfo=TZ))
    lead = LeadRepository(session).add(_lead_from_hit(ctx, mapped))
    _queue_messages(ctx, lead)
    messages = MessageRepository(session).list(lead_id=lead.id)
    assert len(messages) == 1
    return lead, messages[0]


def test_http_source_sin_host_es_none() -> None:
    from worker.defaults import http_source

    assert http_source("http://") is None
    assert http_source("https://") is None


def test_http_source_con_control_o_espacio_es_none() -> None:
    from worker.defaults import http_source

    assert http_source("https://negocio.cl/contacto\n") is None
    assert http_source("https://nego\x00cio.cl/") is None
    assert http_source("https://negocio.cl/contacto uno") is None
    assert http_source("https://negocio.cl/contacto") == "https://negocio.cl/contacto"


def test_hit_sin_fuente_se_rechaza(session: Session) -> None:
    from worker.defaults import place_from_source

    dropped = place_from_source(
        _origen(email_source_url="ftp://negocio.cl/contacto"),
        commune="Providencia",
        category="cafeteria",
    )
    assert dropped is not None
    assert dropped.email_source_url is None
    lead, message = _mensaje_del_hit(session)
    assert lead.contact_email_source_url is None
    assert message.status == "rejected"
    rules = message.check_result["rules"]["reasons"]
    assert "el lead no tiene fuente del correo" in rules


def test_gmail_sin_fuente_no_entra_al_pie(session: Session) -> None:
    lead, message = _mensaje_del_hit(session, email="persona@gmail.com")
    assert lead.contact_email_source_url is None
    assert message.status == "rejected"
    assert "gmail.com" not in message.body_text
    assert "gmail.com" not in (message.body_html or "")


def test_hit_con_fuente_real_la_muestra_en_el_pie(session: Session) -> None:
    source = "https://negocio.cl/contacto"
    lead, message = _mensaje_del_hit(session, email_source_url=source)
    assert lead.contact_email_source_url == source
    assert message.status == "queued"
    assert source in message.body_text
    assert f"obtuvimos su correo de {source}, de acceso público, asociado a su negocio" in (
        message.body_text
    )


def test_followup_no_crea_mensaje_si_esta_suprimido(session: Session) -> None:
    SuppressionRepository(session).add(
        "email",
        "ya-suprimido@example.test",
        reason="baja",
        source="baja",
    )
    lead = _lead(
        session,
        status="enviado",
        business="Taller Sur",
        contact_email="ya-suprimido@example.test",
        contact_email_source_url="https://taller.test/contacto",
    )
    MessageRepository(session).add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="out",
            channel="email_outreach",
            sequence_step=1,
            status="sent",
            subject="Propuesta comercial: landing para Taller Sur",
            body_text="primer envío",
            sent_at=datetime(2026, 3, 2, 15, 0, tzinfo=TZ),
        )
    )
    ctx = _ctx(session, datetime(2026, 3, 20, 11, 0, tzinfo=TZ))
    assert job_followups(ctx) == 0
    rows = MessageRepository(session).list(lead_id=lead.id)
    assert len(rows) == 1
    assert rows[0].sequence_step == 1
    assert rows[0].status == "sent"


def test_scout_no_crea_lead_suprimido(session: Session) -> None:
    SuppressionRepository(session).add(
        "email",
        "ya-suprimido@example.test",
        reason="baja",
        source="baja",
    )

    class Source:
        def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]:
            return [
                PlaceHit(
                    place_id="place-suprimido",
                    name="Taller Sur",
                    formatted_address="Av 1",
                    commune="Providencia",
                    city="Santiago",
                    category="taller-mecanico",
                    website_uri=None,
                    rating=4.8,
                    user_rating_count=40,
                    business_status="OPERATIONAL",
                    email="ya-suprimido@example.test",
                    instagram_handle=None,
                    linkedin_url=None,
                    phone_public=None,
                    estimated_value_clp=350_000,
                    opportunity_score=80,
                    scenario="test",
                    email_source_url="https://taller.test/contacto",
                )
            ]

    ctx = _ctx(session, datetime(2026, 3, 20, 11, 0, tzinfo=TZ))
    ctx.ports.places = Source()  # type: ignore[assignment]
    assert job_scout(ctx) == 0
    assert LeadRepository(session).list(limit=20) == []


def test_pipeline_no_encola_correo_suprimido(session: Session) -> None:
    SuppressionRepository(session).add(
        "email",
        "ya-suprimido@example.test",
        reason="baja",
        source="email",
    )
    lead = _lead(
        session,
        status="video",
        business="Taller Sur",
        contact_email="ya-suprimido@example.test",
        contact_email_source_url="https://taller.test/contacto",
        instagram_handle="tallersur",
        linkedin_url="https://www.linkedin.com/in/tallersur",
        phone_public="+56911112222",
    )
    ctx = _ctx(session, datetime(2026, 3, 20, 11, 0, tzinfo=TZ))
    job_pipeline(ctx)
    assert MessageRepository(session).list(lead_id=lead.id) == []
    stored = LeadRepository(session).get(lead.id)
    assert stored is not None
    assert stored.status == "opt_out"


def test_buzones_genericos_son_la_lista_fija() -> None:
    from core.suppression import generic_local_part

    generic = (
        "contacto",
        "info",
        "consultas",
        "atencion",
        "administracion",
        "gerencia",
        "estudio",
        "correo",
        "oficina",
        "secretaria",
        "recepcion",
        "hola",
        "ventas",
        "comercial",
        "abogados",
        "contabilidad",
        "admin",
    )
    for local in generic:
        assert generic_local_part(f"{local}@estudio.cl")
    assert generic_local_part("Atención@estudio.cl")
    assert generic_local_part("persona@estudio.cl") is False
    assert generic_local_part("hello@estudio.cl") is False


def test_baja_de_contacto_suprime_el_estudio(session: Session) -> None:
    from core.suppression import record_opt_out

    lead = _lead(
        session,
        contact_email="contacto@estudio.test",
        place_id="place-estudio",
    )
    record_opt_out(session, lead, channel="email", reason="baja")
    repo = SuppressionRepository(session)
    assert repo.contains("email", "contacto@estudio.test")
    assert repo.contains("lead", "place-estudio")
    assert repo.contains("domain", "estudio.test") is False


def test_el_extracto_oculta_cita_firma_y_datos(session: Session) -> None:
    from core.suppression import erase_personal_data, record_opt_out

    texto = (
        "Hola, mi fono es +56 9 1111 2222 y el rut 12.345.678-5.\n"
        "Escriban a otro@gmail.com si quieren.\n"
        "Saludos\n"
        "Juan Pérez\n"
        "El lun, 2 mar 2026, Ana escribió:\n"
        "> no reenviar\n"
    )
    lead = _lead(
        session,
        business="Extracto",
        contact_email="persona@estudio.cl",
        phone_public="+56911112222",
        place_id="place-extracto",
    )
    rows = record_opt_out(session, lead, channel="email", reason="baja", text=texto)
    detail = next(row.detail for row in rows if row.kind == "email")
    assert detail is not None
    assert "[teléfono]" in detail
    assert "[rut]" in detail
    assert "[correo]" in detail
    assert "Saludos" not in detail
    assert "escribió" not in detail
    assert ">" not in detail
    assert len(detail) <= 500
    erase_personal_data(session, lead)
    assert lead.contact_email is None
    assert lead.phone_public is None
    assert next(row.detail for row in rows if row.kind == "email") is None
    assert SuppressionRepository(session).contains("email", "persona@estudio.cl") is True
    from core.suppression import is_suppressed

    assert is_suppressed(session, lead) is True


def test_el_dominio_solo_si_es_el_del_sitio(session: Session) -> None:
    from core.suppression import record_opt_out

    texto = "BAJA. No me escriban más."
    propio = _lead(
        session,
        business="Estudio Propio",
        contact_email="persona@estudio.cl",
        website_url="https://estudio.cl/contacto",
        place_id="place-propio",
    )
    rows = record_opt_out(session, propio, channel="email", reason="baja", text=texto)
    assert {row.kind for row in rows} == {"email", "lead", "domain"}
    email_row = next(row for row in rows if row.kind == "email")
    assert email_row.detail == texto
    assert email_row.source == "email"
    assert email_row.created_at is not None
    assert all(row.detail is None for row in rows if row.kind != "email")
    largo = _lead(
        session,
        business="Texto Largo",
        contact_email="otro@estudio.cl",
        place_id="place-largo",
    )
    recorte = record_opt_out(session, largo, channel="email", reason="baja", text="y" * 2500)
    assert len(next(row.detail or "" for row in recorte if row.kind == "email")) == 500
    otra = record_opt_out(session, propio, channel="email", reason="baja")
    assert next(row.detail for row in otra if row.kind == "email") == texto
    from core.suppression import normalize_email

    assert normalize_email("persona@www.estudio.cl") == "persona@www.estudio.cl"
    repo = SuppressionRepository(session)
    assert repo.contains("domain", "www.Estudio.CL.") is True

    vtr = _lead(
        session,
        business="Estudio VTR",
        contact_email="persona@vtr.net",
        website_url="https://estudio.cl",
        place_id="place-vtr",
    )
    assert {row.kind for row in record_opt_out(session, vtr, channel="email", reason="baja")} == {
        "email",
        "lead",
    }
    assert repo.contains("domain", "vtr.net") is False

    sin_sitio = _lead(
        session,
        business="Sin Sitio",
        contact_email="persona@negocio.cl",
        website_url=None,
        place_id="place-sin-sitio",
    )
    assert {
        row.kind for row in record_opt_out(session, sin_sitio, channel="email", reason="baja")
    } == {"email", "lead"}
    assert repo.contains("domain", "negocio.cl") is False


def test_reimport_del_place_sigue_suprimido(session: Session) -> None:
    SuppressionRepository(session).add(
        "lead",
        "place-estudio",
        reason="baja",
        source="email",
    )

    class Source:
        def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]:
            return [
                PlaceHit(
                    place_id="place-estudio",
                    name="Estudio Norte",
                    formatted_address="Av 1",
                    commune="Providencia",
                    city="Santiago",
                    category="estudio-contable",
                    website_uri=None,
                    rating=4.8,
                    user_rating_count=40,
                    business_status="OPERATIONAL",
                    email="otro@correo.test",
                    instagram_handle="estudionorte",
                    linkedin_url=None,
                    phone_public="+56922223333",
                    estimated_value_clp=350_000,
                    opportunity_score=80,
                    scenario="test",
                    email_source_url="https://estudio.test/contacto",
                )
            ]

    ctx = _ctx(session, datetime(2026, 3, 20, 11, 0, tzinfo=TZ))
    ctx.ports.places = Source()  # type: ignore[assignment]
    assert job_scout(ctx) == 0
    assert LeadRepository(session).list(limit=20) == []


def test_place_sin_email_no_se_mapea() -> None:
    from worker.defaults import place_from_source

    class Hit:
        place_id = "abc"
        name = "Café Sin Mail"
        formatted_address = "Av 1"
        business_status = "OPERATIONAL"
        rating = 4.9
        user_rating_count = 40
        website_uri = None
        national_phone_number = "+56911111111"

    assert place_from_source(Hit(), commune="Ñuñoa", category="cafeteria") is None


def test_place_incompleto_no_crea_lead(session: Session) -> None:
    from worker.defaults import _PlacesBridge
    from worker.funnel import job_scout

    class Hit:
        place_id = "abc"
        name = "Café Sin Mail"
        formatted_address = "Av 1"
        business_status = "OPERATIONAL"
        rating = 4.9
        user_rating_count = 40

    class Source:
        def search(self, commune: str, category_slug: str, limit: int) -> list[Hit]:
            return [Hit()]

    ctx = _ctx(session, datetime(2026, 3, 3, 9, 0, tzinfo=TZ))
    ctx.ports.places = _PlacesBridge(Source())  # type: ignore[assignment]
    assert job_scout(ctx) == 0
    assert LeadRepository(session).list(limit=20) == []


def test_prod_con_credencial_usa_adaptadores_reales(monkeypatch: pytest.MonkeyPatch) -> None:
    from worker.defaults import _PlacesBridge, _SmtpBridge, build_default_ports

    monkeypatch.setenv("APP_MODE", "prod")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("OUTREACH_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "dummy-places")
    monkeypatch.setenv("OUTREACH_SMTP_HOST", "smtp.example")
    monkeypatch.setenv("OUTREACH_SMTP_USER", "user")
    monkeypatch.setenv("OUTREACH_SMTP_PASSWORD", "secret")
    reset_settings()
    ports = build_default_ports()
    assert isinstance(ports.places, _PlacesBridge)
    assert isinstance(ports.outreach, _SmtpBridge)
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DRY_RUN", "true")
    reset_settings()
    demo = build_default_ports()
    assert isinstance(demo.places, EmptySource)
    assert isinstance(demo.outreach, GuardedOutreach)


def test_guarded_outreach_no_declara_envio() -> None:
    result = GuardedOutreach().send("1", "a@b.cl", "s", "t", "<p>t</p>")
    assert result.status == "blocked"


def test_drain_queued_corre_el_job(session: Session) -> None:
    row = JobRun(job="metrics_rollup", status="queued", processed=0)
    session.add(row)
    session.flush()
    ctx = _ctx(session, datetime(2026, 3, 3, 12, 0, tzinfo=TZ))
    assert drain_queued(ctx) == 1
    stored = session.get(JobRun, row.id)
    assert stored is not None
    assert stored.status == "ok"
