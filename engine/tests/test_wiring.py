"""Puertos de producción, candado SMTP, IMAP sin intención y checkout Mercado Pago."""

from __future__ import annotations

import smtplib
from collections.abc import Iterator
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app import create_app
from api.deps import LocalPaymentProvider, build_payment_provider
from api.security import hash_password, reset_login_attempts
from core.config import ENGINE_DIR, Settings, reset_settings
from db.models import Event, LlmCall, User
from db.repositories import SettingsRepository
from db.session import create_all, reset_engine, session_scope
from integrations.booking import CalComBooking, CalendlyBooking
from integrations.email.inbound import ImapPoller
from integrations.email.outreach import SmtpOutreach
from integrations.hosting import CaddyHosting
from integrations.meta import MetaCloud
from integrations.notify import OwnerNotifier
from integrations.pagespeed import HttpWebAuditor
from integrations.payments import MercadoPagoProvider, Preference
from integrations.places import GooglePlacesSource
from worker.scheduler import run_job
from worker.testing_ports import (
    EmptyInbound,
    EmptySource,
    GuardedOutreach,
    LocalBooking,
    LocalPayments,
    LogNotifier,
)
from worker.wiring import (
    DisabledBooking,
    DisabledHosting,
    DisabledInbound,
    DisabledMeta,
    DisabledNotifier,
    DisabledOutreach,
    DisabledPayments,
    DisabledPlaces,
    bind_worker_session,
    build_ports,
    channel_status,
    clear_disabled_notes,
    unbind_worker_session,
)

_HTML = '<p>Hola</p><img src="https://evil.test/pixel.gif" width="1" height="1">'
_STUBS = (
    EmptySource,
    GuardedOutreach,
    EmptyInbound,
    LocalBooking,
    LocalPayments,
    LogNotifier,
)
_ADMIN = "admin@example.com"
_PASSWORD = "clave-de-prueba"


@pytest.fixture(autouse=True)
def _aislar() -> Iterator[None]:
    clear_disabled_notes()
    reset_settings()
    reset_engine()
    yield
    clear_disabled_notes()
    reset_settings()
    reset_engine()
    reset_login_attempts()


def _full(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_mode": "prod",
        "dry_run": False,
        "outreach_enabled": True,
        "public_base_url": "https://agencia.example",
        "google_places_api_key": "places-test",
        "pagespeed_api_key": "ps-test",
        "resend_api_key": "re_test",
        "email_tx_from": "tx@example.com",
        "outreach_smtp_host": "smtp.example",
        "outreach_smtp_port": 587,
        "outreach_smtp_user": "smtp-user",
        "outreach_smtp_password": "smtp-secret",
        "outreach_imap_host": "imap.example",
        "outreach_imap_port": 993,
        "outreach_imap_user": "inbox@example.com",
        "outreach_imap_password": "imap-secret",
        "outreach_from": "Agencia <out@example.com>",
        "booking_provider": "calcom",
        "booking_link": "https://cal.example/cita",
        "calcom_webhook_secret": "cal-secret",
        "calendly_webhook_signing_key": "",
        "mp_access_token": "TEST-MP",
        "mp_webhook_secret": "mp-secret",
        "meta_app_secret": "meta-secret",
        "meta_verify_token": "meta-verify",
        "notify_email": "dueno@example.com",
        "telegram_bot_token": "123:abc",
        "telegram_chat_id": "99",
        "hosting_provider": "caddy",
        "ig_access_token": "",
        "whatsapp_token": "",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def _empty(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_mode": "prod",
        "dry_run": False,
        "outreach_enabled": False,
        "public_base_url": "https://agencia.example",
        "google_places_api_key": "",
        "pagespeed_api_key": "",
        "resend_api_key": "",
        "email_tx_from": "",
        "outreach_smtp_host": "",
        "outreach_smtp_user": "",
        "outreach_smtp_password": "",
        "outreach_imap_host": "",
        "outreach_imap_user": "",
        "outreach_imap_password": "",
        "outreach_from": "",
        "booking_provider": "calcom",
        "booking_link": "",
        "calcom_webhook_secret": "",
        "calendly_webhook_signing_key": "",
        "mp_access_token": "",
        "mp_webhook_secret": "",
        "meta_app_secret": "",
        "meta_verify_token": "",
        "notify_email": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "hosting_provider": "caddy",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def _use_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'wiring.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_MODE", "prod")
    monkeypatch.setenv("DRY_RUN", "false")
    reset_settings()
    reset_engine()
    create_all()


class _Grab:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> str:
        self.messages.append(message)
        return "grabbed"


def _boom(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("socket")


def _html_part(message: EmailMessage) -> str:
    for part in message.walk():
        if part.get_content_type() == "text/html":
            content = part.get_content()
            return content if isinstance(content, str) else str(content)
    return ""


def _assert_headers(message: EmailMessage) -> None:
    assert message["Reply-To"] == "inbox@example.com"
    assert message["List-Unsubscribe"] == "<https://agencia.example/baja?mid=m1>"
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    raw = message.as_string().lower()
    assert "<img" not in raw
    assert "pixel" not in raw
    assert "evil.test" not in _html_part(message).lower()


def _forbid_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smtplib, "SMTP", _boom)
    monkeypatch.setattr("integrations.email.outreach.smtplib.SMTP", _boom)
    monkeypatch.setattr("integrations.email.inbound.imaplib.IMAP4_SSL", _boom)


def test_prod_ports_no_son_stubs(block_network: None) -> None:
    ports = build_ports(_full())
    assert type(ports.places) is GooglePlacesSource
    assert type(ports.outreach) is SmtpOutreach
    assert type(ports.inbound) is ImapPoller
    assert type(ports.bookings) is CalComBooking
    assert type(ports.payments) is MercadoPagoProvider
    assert type(ports.notifier) is OwnerNotifier
    assert type(ports.auditor) is HttpWebAuditor
    assert type(ports.hosting) is CaddyHosting
    assert type(ports.meta) is MetaCloud
    calendly = _full(
        booking_provider="calendly",
        calendly_webhook_signing_key="cal-sign",
    )
    assert type(build_ports(calendly).bookings) is CalendlyBooking

    empty = build_ports(_empty())
    disabled = (
        empty.places,
        empty.outreach,
        empty.inbound,
        empty.bookings,
        empty.payments,
        empty.notifier,
        empty.meta,
    )
    assert type(empty.places) is DisabledPlaces
    assert type(empty.outreach) is DisabledOutreach
    assert type(empty.inbound) is DisabledInbound
    assert type(empty.bookings) is DisabledBooking
    assert type(empty.payments) is DisabledPayments
    assert type(empty.notifier) is DisabledNotifier
    assert type(empty.meta) is DisabledMeta
    assert type(empty.hosting) is CaddyHosting
    assert type(empty.auditor) is HttpWebAuditor
    for port in disabled:
        assert not isinstance(port, _STUBS)
        assert not type(port).__name__.startswith(("Empty", "Local", "Log", "Guarded"))
    cloud = build_ports(_empty(hosting_provider="cloudflare_pages"))
    assert type(cloud.hosting) is DisabledHosting

    demo = build_ports(_full(app_mode="demo", dry_run=False))
    assert type(demo.places) is EmptySource
    assert type(demo.outreach) is GuardedOutreach
    assert type(demo.inbound) is EmptyInbound
    assert type(demo.bookings) is LocalBooking
    assert type(demo.payments) is LocalPayments
    assert type(demo.notifier) is LogNotifier


def test_estado_de_canales() -> None:
    live = channel_status(_full())
    assert set(live) == {
        "places",
        "auditor",
        "outreach",
        "inbound",
        "booking",
        "payments",
        "hosting",
        "meta",
        "notifier",
        "email_tx",
    }
    assert set(live.values()) == {"real"}
    assert channel_status(_full(app_mode="demo", dry_run=False)) == dict.fromkeys(live, "dry_run")
    assert channel_status(_full(dry_run=True)) == dict.fromkeys(live, "dry_run")
    missing = channel_status(_empty())
    assert missing["places"] == "deshabilitado: falta GOOGLE_PLACES_API_KEY"
    assert missing["payments"] == "deshabilitado: falta MP_ACCESS_TOKEN"
    assert missing["notifier"].startswith("deshabilitado: falta NOTIFY_EMAIL")
    assert "TELEGRAM_BOT_TOKEN" in missing["notifier"]
    assert missing["auditor"] == "real"
    assert missing["hosting"] == "real"
    dry_gap = channel_status(_empty(dry_run=True))
    assert dry_gap["places"].startswith("deshabilitado: falta ")
    assert dry_gap["auditor"] == "dry_run"
    assert dry_gap["hosting"] == "dry_run"


def test_disabled_avisa_una_vez_y_no_abre_socket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    block_network: None,
) -> None:
    _forbid_smtp(monkeypatch)
    monkeypatch.setattr("integrations.places.base.httpx.Client", _boom)
    monkeypatch.setattr("integrations.payments.base.httpx.post", _boom)
    monkeypatch.setattr("integrations.payments.base.httpx.get", _boom)
    _use_db(monkeypatch, tmp_path)
    ports = build_ports(_empty())
    with session_scope() as session:
        token = bind_worker_session(session)
        try:
            assert ports.places.search("Ñuñoa", "cafeteria", 3) == []
            sent = ports.outreach.send("1", "a@b.cl", "s", "t", "<p>t</p>")
            assert sent.status == "blocked"
            assert ports.inbound.poll() == []
            assert ports.bookings.link_for("lead") == ""
            assert ports.bookings.poll() == []
            pref = ports.payments.create_preference("ord", "Anticipo", 1000)
            assert pref.url == ""
            assert pref.preference_id == ""
            assert ports.payments.poll() == []
            ports.notifier.send_digest("hola")
            assert ports.meta.parse_webhook(b"{}", "sig") == []  # type: ignore[attr-defined]
            ports.places.search("Ñuñoa", "cafeteria", 3)
        finally:
            unbind_worker_session(token)
    with session_scope() as session:
        rows = list(session.scalars(select(Event).where(Event.level == "warn")).all())
        llm = session.scalar(select(func.count()).select_from(LlmCall))
    assert llm == 0
    agents = {row.agent for row in rows}
    assert agents == {"places", "outreach", "inbound", "booking", "payments", "notifier", "meta"}
    assert all(row.message.startswith("canal deshabilitado: falta ") for row in rows)
    assert len(rows) == len(agents)
    clear_disabled_notes()
    with session_scope() as session:
        token = bind_worker_session(session)
        try:
            ports.outreach.send("2", "a@b.cl", "s", "t", "<p>t</p>")
        finally:
            unbind_worker_session(token)
        again = session.scalar(select(func.count()).select_from(Event).where(Event.level == "warn"))
    assert again == len(agents)


def test_places_suspend_network_no_abre_socket(block_network: None) -> None:
    source = GooglePlacesSource("places-test", suspend_network=True)
    assert source.search("Ñuñoa", "cafeteria", 3) == []


def test_outreach_bloquea_sin_socket_con_candado_cerrado(
    monkeypatch: pytest.MonkeyPatch,
    block_network: None,
) -> None:
    _forbid_smtp(monkeypatch)
    cases = (
        {"dry_run": True},
        {"app_mode": "demo", "dry_run": False},
        {"outreach_enabled": False},
        {"outreach_smtp_password": ""},
    )
    for overrides in cases:
        grab = _Grab()
        mailer = SmtpOutreach(_full(**overrides), kill_switch=True, transport=grab)
        result = mailer.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML)
        assert result.status == "blocked"
        assert grab.messages == []
    grab = _Grab()
    closed = SmtpOutreach(_full(), kill_switch=False, transport=grab)
    assert closed.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML).status == "blocked"
    assert grab.messages == []


def test_outreach_entrega_con_candado_abierto(monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_smtp(monkeypatch)
    grab = _Grab()
    mailer = SmtpOutreach(_full(), kill_switch=True, transport=grab)
    sent = mailer.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML)
    assert sent.status == "sent"
    assert sent.provider_message_id == "grabbed"
    assert len(grab.messages) == 1
    _assert_headers(grab.messages[0])


def test_wiring_abre_el_candado_con_kill_switch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _forbid_smtp(monkeypatch)
    _use_db(monkeypatch, tmp_path)
    grab = _Grab()
    with session_scope() as session:
        SettingsRepository(session).put("kill_switch", True, updated_by="test")
        ports = build_ports(_full(), session=session)
        assert type(ports.outreach) is SmtpOutreach
        ports.outreach._transport = grab  # type: ignore[attr-defined]
        sent = ports.outreach.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML)
    assert sent.status == "sent"
    assert len(grab.messages) == 1
    _assert_headers(grab.messages[0])


def test_imap_poller_deja_el_intent_vacio(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = (
        b"Message-ID: <in-1@example.com>\r\n"
        b"From: Cliente <cliente@negocio.cl>\r\n"
        b"To: inbox@example.com\r\n"
        b"Subject: Re: propuesta\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"BAJA\r\n"
    )

    class _FakeSSL:
        def __init__(self, host: str, port: int) -> None:
            assert host == "imap.example"
            assert port == 993

        def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
            del user, password
            return "OK", []

        def select(self, mailbox: str) -> tuple[str, list[bytes]]:
            del mailbox
            return "OK", [b"1"]

        def search(self, charset: object, criteria: str) -> tuple[str, list[bytes]]:
            del charset, criteria
            return "OK", [b"7"]

        def fetch(self, uid: bytes, spec: str) -> tuple[str, list[tuple[bytes, bytes]]]:
            del uid, spec
            return "OK", [(b"7 (RFC822)", raw)]

        def logout(self) -> tuple[str, list[bytes]]:
            return "OK", []

    monkeypatch.setattr("integrations.email.inbound.imaplib.IMAP4_SSL", _FakeSSL)
    found = ImapPoller(_full()).poll()
    assert len(found) == 1
    assert found[0].intent == ""
    assert found[0].from_email == "cliente@negocio.cl"
    assert found[0].body == "BAJA"
    assert ImapPoller(_full(dry_run=True)).poll() == []


def test_notifier_real_no_sale_en_dry_run() -> None:
    posts: list[dict[str, object]] = []
    sent: list[str] = []

    class _Mail:
        def send(
            self,
            to: str,
            subject: str,
            text: str,
            html: str,
            headers: dict[str, str],
            *,
            consent: bool = False,
            kind: str = "",
        ) -> object:
            del subject, text, headers, kind
            assert consent is True
            assert "<img" not in html.lower()
            sent.append(to)
            return None

    dry = OwnerNotifier(
        _full(dry_run=True), mailer=_Mail(), post=lambda _url, payload: posts.append(payload)
    )
    dry.send_digest("hola")
    assert sent == []
    assert posts == []
    live = OwnerNotifier(_full(), mailer=_Mail(), post=lambda _url, payload: posts.append(payload))
    live.send_digest("hola <b>")
    assert sent == ["dueno@example.com"]
    assert posts and posts[0]["chat_id"] == "99"
    assert "hola" in str(posts[0]["text"])


def test_checkout_prod_usa_mercadopago() -> None:
    prod = build_payment_provider(_full())
    assert type(prod) is MercadoPagoProvider
    demo = build_payment_provider(_full(app_mode="demo", dry_run=False))
    assert type(demo) is LocalPaymentProvider
    dry = build_payment_provider(_full(dry_run=True))
    assert type(dry) is LocalPaymentProvider
    missing = build_payment_provider(_full(mp_access_token=""))
    assert type(missing) is LocalPaymentProvider
    sample = Preference(
        preference_id="pref-1",
        checkout_url="https://pay.example/pref-1",
        order_id="ord",
        amount_clp=1000,
    )
    assert sample.id == "pref-1"
    assert sample.url == "https://pay.example/pref-1"


def test_scheduler_prod_usa_build_ports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = {"ports": 0, "default": 0}

    def spy_ports(settings: Settings, session: Session | None = None) -> object:
        del settings, session
        calls["ports"] += 1
        from worker.testing_ports import build_default_ports

        return build_default_ports()

    def spy_default() -> object:
        calls["default"] += 1
        from worker.testing_ports import build_default_ports

        return build_default_ports()

    monkeypatch.setattr("worker.scheduler.build_ports", spy_ports)
    monkeypatch.setattr("worker.scheduler.build_default_ports", spy_default)
    _use_db(monkeypatch, tmp_path)
    run_job("demo_expiry")
    assert calls == {"ports": 1, "default": 0}


def test_scheduler_demo_conserva_los_stubs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("build_ports en demo")

    monkeypatch.setattr("worker.scheduler.build_ports", boom)
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'demo.db').as_posix()}")
    reset_settings()
    reset_engine()
    create_all()
    run_job("demo_expiry")


def test_api_agents_expone_el_estado_de_cada_canal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("OUTREACH_ENABLED", "false")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_EMAIL", _ADMIN)
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost")
    reset_settings()
    reset_engine()
    reset_login_attempts()
    app = create_app()
    with TestClient(app) as client:
        with session_scope() as session:
            session.add(User(email=_ADMIN, password_hash=hash_password(_PASSWORD)))
        logged = client.post("/api/auth/login", json={"email": _ADMIN, "password": _PASSWORD})
        assert logged.status_code == 200, logged.text
        response = client.get("/api/agents")
    assert response.status_code == 200, response.text
    rows = response.json()
    stems = {path.stem for path in (ENGINE_DIR / "prompts").glob("*.md")}
    assert {row["name"] for row in rows} == stems
    assert rows
    expected = channel_status(Settings(_env_file=None, app_mode="demo", dry_run=True))
    for row in rows:
        assert row["channels"] == expected
        assert set(row["channels"].values()) == {"dry_run"}
