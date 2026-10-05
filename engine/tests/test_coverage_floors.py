"""Ramas que la suite no pisaba: cierre, entrega, servicios y digest."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.closer import CloserAgent, _money, _package, _wants_to_buy
from agents.context import AgentContext
from agents.delivery import DeliveryAgent
from api.deps import LocalPaymentProvider, PaymentFact
from api.errors import ApiError
from api.schemas import LeadPatch, SettingsIn
from api.security import make_baja_token
from api.services import (
    _as_bool,
    _expected_amounts,
    _find_lead_id,
    _maybe_schedule,
    _open_balance,
    _packages_view,
    _payment_kind,
    _price_of,
    _send_delivery_mail,
    add_suppression,
    agent_rows,
    apply_baja,
    apply_payment,
    approve_hitl,
    approve_project_public,
    checkout,
    delete_suppression,
    domain_authorized,
    edit_hitl,
    enqueue_action,
    lead_detail,
    list_approvals,
    list_data_requests,
    list_events,
    list_leads,
    list_messages,
    list_orders,
    list_projects,
    list_suppression,
    load_demo,
    manual_queue,
    mark_manual_sent,
    metrics,
    patch_data_request,
    patch_lead,
    patch_project,
    project_by_token,
    read_settings_view,
    reject_hitl,
    reply_thread,
    save_feedback,
    save_intake,
    submit_contacto,
    submit_rights,
    threads,
    transition_from_admin,
    write_settings,
)
from api.yamlutil import dump_yaml
from core.config import Settings, reset_settings
from db.models import Approval, Artifact, Event, Lead, Message, Order, Project
from db.repositories import LeadRepository, SettingsRepository
from db.session import create_all, reset_engine, session_scope
from integrations.notify import (
    OwnerNotifier,
    _default_post,
    email_digest_ready,
    notifier_missing,
    telegram_digest_ready,
)


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
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'cov.db').as_posix()}")
    monkeypatch.setenv("AGENCY_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("CLIENT_SITES_DIR", str(tmp_path / "sites"))
    monkeypatch.setenv("AGENCY_NAME", "[datos de la agencia]")
    monkeypatch.setenv("AGENCY_EMAIL", "hola@example.com")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost")
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setenv("SECRET_KEY", "clave-de-cobertura-con-32-caracteres")
    reset_settings()
    reset_engine()
    create_all()
    return tmp_path


@pytest.fixture
def session(env: Path) -> object:
    del env
    with session_scope() as current:
        yield current


def _lead(session: Session, **overrides: object) -> Lead:
    data: dict[str, object] = {
        "source": "outbound_demo",
        "business": "Café Cobertura",
        "category": "cafeteria",
        "city": "Santiago",
        "commune": "Providencia",
        "opportunity_score": 70,
        "status": "nuevo",
        "estimated_value_clp": 350_000,
        "high_value": False,
        "tone": "tu",
        "contact_email": "cafe@cobertura-ejemplo.cl",
        "contact_email_source_url": "http://localhost/contacto",
    }
    data.update(overrides)
    return LeadRepository(session).add(Lead(**data))


def _order(session: Session, lead: Lead, **overrides: object) -> Order:
    data: dict[str, object] = {
        "lead_id": lead.id,
        "package_code": "landing_pro",
        "amount_clp": 294_118,
        "iva_clp": 55_882,
        "total_clp": 350_000,
        "deposit_percent": 50,
        "status": "pending",
    }
    data.update(overrides)
    order = Order(**data)
    session.add(order)
    session.flush()
    return order


def _project(session: Session, lead: Lead, order: Order, **overrides: object) -> Project:
    data: dict[str, object] = {
        "order_id": order.id,
        "lead_id": lead.id,
        "status": "intake_pendiente",
        "revisions_used": 0,
        "max_revisions": 2,
        "portal_token": f"portal-{lead.id[:8]}",
    }
    data.update(overrides)
    project = Project(**data)
    session.add(project)
    session.flush()
    return project


def _ctx(session: Session, lead_id: str | None) -> AgentContext:
    return AgentContext(session, lead_id=lead_id)


def test_closer_salta_sin_lead_sin_intencion_y_sin_precio(
    session: Session,
    block_network: None,
) -> None:
    del block_network
    assert CloserAgent().run(_ctx(session, None)).output == {"skipped": True}
    missing = CloserAgent().run(_ctx(session, "no-existe"))
    assert missing.output == {"skipped": True}
    quiet = _lead(session, status="respondio", business="Callado")
    assert CloserAgent().run(_ctx(session, quiet.id)).output == {"skipped": True}
    assert _wants_to_buy(_ctx(session, quiet.id), quiet.id) is False
    session.add(
        Message(
            lead_id=quiet.id,
            thread_id=quiet.id,
            direction="in",
            channel="email_outreach",
            status="received",
            body_text="Me interesa",
            intent="interesado",
        )
    )
    session.flush()
    assert _wants_to_buy(_ctx(session, quiet.id), quiet.id) is True

    parked = _lead(session, status="nuevo", business="Fuera")
    assert CloserAgent().run(_ctx(session, parked.id)).output == {"skipped": True}

    booked = _lead(session, status="agendado", business="Ya tiene orden")
    _order(session, booked)
    assert CloserAgent().run(_ctx(session, booked.id)).output == {"skipped": True}

    alto = _lead(session, status="agendado", business="Cadena", high_value=True)
    alto_result = CloserAgent().run(_ctx(session, alto.id))
    assert alto_result.output == {"sent": False}
    assert LeadRepository(session).get(alto.id).status == "revision"  # type: ignore[union-attr]
    approval = session.scalar(select(Approval).where(Approval.lead_id == alto.id))
    assert approval is not None
    assert approval.kind == "deal_alto_valor"

    sede = _lead(
        session,
        status="agendado",
        business="Varias sedes",
        diagnosis={"recommended_package": "multi_sede"},
    )
    sede_result = CloserAgent().run(_ctx(session, sede.id))
    assert sede_result.output == {"sent": False}
    fuera = session.scalar(
        select(Approval).where(Approval.lead_id == sede.id, Approval.kind == "fuera_de_alcance")
    )
    assert fuera is not None

    assert _package(None) == "landing_esencial"
    assert _package({"recommended_package": "otro"}) == "landing_esencial"
    assert _money(100_000, False) == (100_000, 19_000, 119_000)


def test_delivery_abre_el_portal_y_salta_los_casos_vacios(
    session: Session,
    block_network: None,
) -> None:
    del block_network
    assert DeliveryAgent().run(_ctx(session, None)).output == {"skipped": True}
    assert DeliveryAgent().run(_ctx(session, "no-existe")).output == {"skipped": True}
    nuevo = _lead(session, status="nuevo", business="Aun no")
    assert DeliveryAgent().run(_ctx(session, nuevo.id)).output == {"skipped": True}

    repetido = _lead(session, status="pagado", business="Ya hay portal")
    orden_repetida = _order(session, repetido, status="deposit_paid")
    _project(session, repetido, orden_repetida)
    assert DeliveryAgent().run(_ctx(session, repetido.id)).output == {"skipped": True}

    sin_orden = _lead(session, status="pagado", business="Sin orden")
    vacio = DeliveryAgent().run(_ctx(session, sin_orden.id))
    assert vacio.ok is False
    assert vacio.events == ["sin orden"]

    listo = _lead(session, status="pagado", business="Listo para portal")
    _order(session, listo, status="deposit_paid")
    hecho = DeliveryAgent().run(_ctx(session, listo.id))
    assert hecho.ok is True
    assert hecho.output["portal_path"].startswith("/proyecto/")
    assert LeadRepository(session).get(listo.id).status == "en_produccion"  # type: ignore[union-attr]


def test_yaml_cubre_escalares_listas_y_mapas() -> None:
    text = dump_yaml(
        {
            "vacio": {},
            "lista_vacia": [],
            "nulo": None,
            "flag": True,
            "off": False,
            "n": 2,
            "precio": 1.5,
            "nombre": "café",
            "anidado": {"clave": ["uno", {"dos": 2}]},
            "items": [{"id": 1}, "plano", []],
        }
    )
    assert "café" in text
    assert text.endswith("\n")
    assert "null" in text
    assert "{}" in text
    assert "[]" in text


def test_digest_avisa_lo_que_falta_y_no_abre_la_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("NOTIFY_EMAIL", "")
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("EMAIL_TX_FROM", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    reset_settings()
    vacio = Settings()
    assert notifier_missing(vacio)
    assert email_digest_ready(vacio) is False
    assert telegram_digest_ready(vacio) is False
    con_correo = Settings(notify_email="dueno@example.com")
    assert "RESEND_API_KEY" in notifier_missing(con_correo)
    assert "EMAIL_TX_FROM" in notifier_missing(con_correo)
    con_token = Settings(telegram_bot_token="token-de-prueba")
    assert notifier_missing(con_token) == ["NOTIFY_EMAIL", "TELEGRAM_CHAT_ID"]

    posted: list[tuple[str, dict[str, object]]] = []

    def _post(url: str, **kwargs: object) -> None:
        posted.append((url, kwargs))

    monkeypatch.setattr(httpx, "post", _post)
    _default_post("http://127.0.0.1/no", {"ok": True})
    assert posted[0][1]["json"] == {"ok": True}

    prod = Settings(
        app_mode="prod",
        dry_run=False,
        secret_key="clave-de-cobertura-con-32-caracteres",
        database_url="sqlite:///./state/digest.db",
        admin_email="admin@example.com",
        admin_password_hash="hash",
        public_base_url="https://example.com",
        agency_name="[datos de la agencia]",
        agency_email="hola@example.com",
        notify_email="dueno@example.com",
        resend_api_key="re_test",
        email_tx_from="avisos@example.com",
        telegram_bot_token="token-de-prueba",
        telegram_chat_id="1",
    )

    class _Mail:
        def __init__(self, fail: bool = False) -> None:
            self.fail = fail
            self.sent = 0

        def send(self, *_args: object, **_kwargs: object) -> None:
            if self.fail:
                raise RuntimeError("correo")
            self.sent += 1

    class _Boom:
        def __call__(self, _url: str, _payload: dict[str, object]) -> None:
            raise RuntimeError("telegram")

    mail = _Mail()
    OwnerNotifier(prod, mailer=mail, post=_post).send_digest("hola")
    assert mail.sent == 1
    OwnerNotifier(prod, mailer=_Mail(fail=True), post=_Boom()).send_digest("falla")
    OwnerNotifier(
        Settings(
            app_mode="prod",
            dry_run=False,
            secret_key="clave-de-cobertura-con-32-caracteres",
            database_url="sqlite:///./state/digest.db",
            admin_email="admin@example.com",
            admin_password_hash="hash",
            public_base_url="https://example.com",
            agency_name="[datos de la agencia]",
            agency_email="hola@example.com",
        )
    ).send_digest("sin canales")


def test_servicios_de_lectura_y_ajustes(session: Session) -> None:
    repo = SettingsRepository(session)
    repo.put(
        "prices",
        {"landing_pro": {"price_clp": 350_000}, "multi_sede": None},
        updated_by="t",
    )
    repo.put(
        "hitl_response_rate_by_channel",
        {"email_outreach": "0.2", "roto": "no"},
        updated_by="t",
    )
    view = _packages_view(session)
    assert any(row["code"] == "multi_sede" and row["price_clp"] is None for row in view)
    assert _price_of(session, "landing_pro") == 350_000
    with pytest.raises(ApiError):
        _price_of(session, "no-existe")
    assert _as_bool(1) is True
    assert _as_bool("x") is False
    rates = read_settings_view(session)["hitl_response_rate_by_channel"]
    assert rates["email_outreach"] == 0.2
    assert "roto" not in rates
    written = write_settings(
        session,
        "admin@example.com",
        SettingsIn(
            kill_switch=True,
            quotas={"email_outreach_daily_limit": 15},
            prices={"landing_esencial": 250_000},
            hitl_response_rate_by_channel={"email_outreach": 0.12},
        ),
    )
    assert written["kill_switch"] is True


def test_contacto_baja_checkout_y_portales(session: Session, env: Path) -> None:
    contacto = submit_contacto(
        session,
        name="Ana",
        email="ana@contacto-ejemplo.cl",
        message="Quiero una landing",
        ip="127.0.0.1",
    )
    assert contacto["status"] == "respondio"
    with pytest.raises(ApiError):
        submit_rights(session, kind="otro", email="ana@contacto-ejemplo.cl", details="")
    derecho = submit_rights(
        session,
        kind="acceso",
        email="ana@contacto-ejemplo.cl",
        details="copia",
    )
    assert derecho["status"]

    alto = _lead(session, status="agendado", business="Cadena Norte", high_value=True)
    provider = LocalPaymentProvider("http://localhost")
    with pytest.raises(ApiError):
        checkout(session, provider, package_code="no-existe", lead_id=alto.id)
    with pytest.raises(ApiError):
        checkout(session, provider, package_code="landing_pro", lead_id=None)
    with pytest.raises(ApiError):
        checkout(session, provider, package_code="landing_pro", lead_id="ausente")
    held = checkout(session, provider, package_code="landing_pro", lead_id=alto.id)
    assert held["checkout_url"]
    assert LeadRepository(session).get(alto.id).status == "revision"  # type: ignore[union-attr]

    baja = _lead(session, status="enviado", business="Se va", contact_email="seva@ejemplo.cl")
    assert apply_baja(session, make_baja_token(baja.id)) == {"ok": True}
    assert LeadRepository(session).get(baja.id).status == "opt_out"  # type: ignore[union-attr]

    demo_lead = _lead(session, business="Demo vieja")
    session.add(
        Artifact(
            lead_id=demo_lead.id,
            kind="landing_demo",
            path="no/esta.html",
            public_token="demo-ausente",
        )
    )
    session.add(
        Artifact(
            lead_id=demo_lead.id,
            kind="landing_demo",
            path="no/esta.html",
            public_token="demo-vieja",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    session.flush()
    assert load_demo(session, "demo-ausente")[0] == 404
    assert load_demo(session, "demo-vieja")[0] == 410
    with pytest.raises(ApiError):
        project_by_token(session, "portal-ausente")

    espera = _lead(session, status="nuevo", business="Intake tarde")
    orden = _order(session, espera)
    portal = _project(session, espera, orden, portal_token="portal-tarde")
    assert save_intake(session, portal.portal_token, {"objetivo": "horario"}) == {"ok": True}
    assert save_feedback(session, portal.portal_token, "más fotos")["status"] == "accepted"
    portal.max_revisions = 1
    session.flush()
    assert save_feedback(session, portal.portal_token, "otra")["status"] == "fuera_de_alcance"

    sin_mail = _lead(session, business="Sin correo", contact_email=None, status="entregado")
    _send_delivery_mail(session, sin_mail, "http://localhost/sitio")
    pago = _lead(session, status="pagado", business="Aun no revisa")
    orden_pago = _order(session, pago, status="pending")
    proyecto = _project(session, pago, orden_pago, portal_token="portal-pronto")
    with pytest.raises(ApiError):
        approve_project_public(session, proyecto.portal_token)

    revisa = _lead(session, status="en_revision_cliente", business="Falta pago")
    orden_revisa = _order(session, revisa, status="pending")
    proyecto_revisa = _project(session, revisa, orden_revisa, portal_token="portal-pago")
    with pytest.raises(ApiError):
        approve_project_public(session, proyecto_revisa.portal_token)

    saldo = _lead(session, status="en_revision_cliente", business="Saldo ya abierto")
    orden_saldo = _order(session, saldo, status="deposit_paid")
    proyecto_saldo = _project(
        session,
        saldo,
        orden_saldo,
        portal_token="portal-saldo",
        intake={"client_approved": True},
    )
    assert _open_balance(session, proyecto_saldo, saldo, orden_saldo)["status"] == "saldo_pendiente"
    assert domain_authorized(session, "") is False
    assert domain_authorized(session, "https://www.ejemplo.cl/ruta") is False
    session.add(
        Project(
            order_id=_order(session, _lead(session, business="Vacio dominio")).id,
            lead_id=saldo.id,
            status="publicado",
            revisions_used=0,
            max_revisions=1,
            domain="",
            portal_token="portal-vacio",
        )
    )
    publicado = _project(
        session,
        _lead(session, business="Dominio propio"),
        _order(session, saldo),
        status="publicado",
        domain="ejemplo.cl",
        portal_token="portal-dominio",
    )
    del publicado
    session.flush()
    assert domain_authorized(session, "https://www.ejemplo.cl/inicio") is True
    del env


def test_admin_consulta_edita_y_encola(session: Session) -> None:
    lead = _lead(session, business="Café Buscado", commune="Ñuñoa")
    session.add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="in",
            channel="email_outreach",
            status="received",
            body_text="hola",
        )
    )
    session.add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="out",
            channel="email_outreach",
            status="sent",
            body_text="enviado",
        )
    )
    session.add(
        Message(
            lead_id=lead.id,
            thread_id="manual-1",
            direction="out",
            channel="instagram",
            status="manual_pending",
            body_text="borrador",
        )
    )
    session.add(Event(agent="diagnoser", level="error", message="falló el prompt", meta={}))
    session.flush()
    found = list_leads(session, status="nuevo", q="café", page=0, page_size=0)
    assert found["total"] >= 1
    assert found["page"] == 1
    detail = lead_detail(session, lead.id)
    assert detail["messages"]
    with pytest.raises(ApiError):
        lead_detail(session, "ausente")
    patched = patch_lead(session, lead.id, LeadPatch(tone="usted"))
    assert patched["id"] == lead.id
    assert LeadRepository(session).get(lead.id).tone == "usted"  # type: ignore[union-attr]
    with pytest.raises(ApiError):
        patch_lead(session, lead.id, LeadPatch(tone="vos"))
    with pytest.raises(ApiError):
        patch_lead(session, "ausente", LeadPatch())
    moved = transition_from_admin(session, lead.id, "perdido", "no responde")
    assert moved["status"] == "perdido"
    with pytest.raises(ApiError):
        transition_from_admin(session, "ausente", "perdido", "no")

    approval = Approval(lead_id=lead.id, kind="compliance", payload={}, status="pending")
    session.add(approval)
    session.flush()
    assert list_approvals(session, "pending")
    with pytest.raises(ApiError):
        approve_hitl(session, "no", "admin@example.com")
    reject_hitl(session, approval.id, "admin@example.com", "no")
    with pytest.raises(ApiError):
        reject_hitl(session, approval.id, "admin@example.com", "otra")
    with pytest.raises(ApiError):
        approve_hitl(session, approval.id, "admin@example.com")

    mensaje = Message(
        lead_id=lead.id,
        thread_id=lead.id,
        direction="out",
        channel="email_outreach",
        status="checking",
        body_text="texto",
        subject="asunto",
    )
    session.add(mensaje)
    session.flush()
    editable = Approval(
        lead_id=lead.id,
        kind="compliance",
        payload={"message_id": mensaje.id},
        status="pending",
    )
    session.add(editable)
    session.flush()
    edited = edit_hitl(
        session,
        editable.id,
        "admin@example.com",
        body_text="nuevo",
        subject="otro",
        message_id=None,
    )
    assert edited["status"] == "edited"
    cerrada = Approval(lead_id=lead.id, kind="compliance", payload={}, status="approved")
    sin_mensaje = Approval(lead_id=lead.id, kind="compliance", payload={}, status="pending")
    session.add(cerrada)
    session.add(sin_mensaje)
    session.flush()
    with pytest.raises(ApiError):
        edit_hitl(
            session,
            "no",
            "admin@example.com",
            body_text=None,
            subject=None,
            message_id=None,
        )
    with pytest.raises(ApiError):
        edit_hitl(
            session,
            cerrada.id,
            "admin@example.com",
            body_text="x",
            subject=None,
            message_id=None,
        )
    with pytest.raises(ApiError):
        edit_hitl(
            session,
            sin_mensaje.id,
            "admin@example.com",
            body_text=None,
            subject=None,
            message_id=None,
        )

    assert manual_queue(session)
    manual = session.scalar(select(Message).where(Message.thread_id == "manual-1"))
    assert manual is not None
    marked = mark_manual_sent(session, manual.id)
    assert marked["status"] == "manual_sent"
    with pytest.raises(ApiError):
        mark_manual_sent(session, marked["id"])
    with pytest.raises(ApiError):
        mark_manual_sent(session, "no")
    assert threads(session)
    assert list_messages(session, lead.id)
    reply = reply_thread(session, lead.id, "respuesta")
    assert reply["status"] == "checking"
    with pytest.raises(ApiError):
        reply_thread(session, "hilo-ausente", "no")

    assert agent_rows(session)
    queued = enqueue_action(session, "metrics_rollup", "admin@example.com")
    assert queued["status"] == "queued"
    assert list_events(session, level="info", agent="api", limit=0)
    numbers = metrics(session)
    assert numbers["response_rate_by_channel"]["email_outreach"] == 1.0
    orden = _order(session, lead)
    assert list_orders(session)
    proyecto = _project(session, lead, orden, portal_token="portal-admin")
    assert list_projects(session)
    changed = patch_project(
        session,
        proyecto.id,
        {"domain": "ejemplo.cl", "intake": {"nota": "ok"}, "status": "en_produccion"},
    )
    assert changed["status"] == "en_produccion"
    with pytest.raises(ApiError):
        patch_project(session, proyecto.id, {"status": "inventado"})
    with pytest.raises(ApiError):
        patch_project(session, "no", {})

    with pytest.raises(ApiError):
        add_suppression(session, "otro", "a@b.cl", "manual")
    added = add_suppression(session, "email", "a@b.cl", "manual")
    assert list_suppression(session)
    delete_suppression(session, added["id"])
    with pytest.raises(ApiError):
        delete_suppression(session, "no")

    rights = submit_rights(session, kind="acceso", email="titular@ejemplo.cl", details="ver")
    assert list_data_requests(session)
    assert patch_data_request(session, rights["id"], "done")["status"] == "done"
    with pytest.raises(ApiError):
        patch_data_request(session, rights["id"], "inventado")
    with pytest.raises(ApiError):
        patch_data_request(session, "no", "open")

    assert _find_lead_id("no") is None
    assert _find_lead_id({"lead_id": lead.id}) == lead.id
    assert _find_lead_id({"metadata": {"lead_id": lead.id}}) == lead.id
    assert _find_lead_id({"payload": {"lead_id": lead.id}}) == lead.id
    _maybe_schedule(session, b"\xff")
    _maybe_schedule(session, b"{}")
    _maybe_schedule(session, b'{"lead_id":"ausente"}')
    pendiente = _order(
        session, _lead(session, status="deposit_paid", business="Saldo"), status="deposit_paid"
    )
    assert _expected_amounts(pendiente) == [175_000]
    assert _payment_kind(pendiente, 1) is None
    ignored = apply_payment(
        session,
        PaymentFact(provider_payment_id="sin-orden", status="approved", amount_clp=1000),
    )
    assert ignored["ignored"] is True
