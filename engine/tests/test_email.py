"""Correo: candado de outreach, baja de un clic y transaccional con consentimiento."""

from __future__ import annotations

import random
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.config import Settings
from db.models import Base
from db.repositories import SettingsRepository
from integrations.email import (
    FakeInbound,
    FakeOutreach,
    FakeTransactional,
    ImapPoller,
    InboundMail,
    ResendTransactional,
    SmtpOutreach,
    build_inbound_poller,
    build_outreach_email,
    build_transactional_email,
)
from integrations.email.resend_mail import RESEND_URL

_HTML = '<p>Hola</p><img src="https://evil.test/pixel.gif" width="1" height="1">'
_RAW = (
    b"Message-ID: <in-1@example.com>\r\n"
    b"From: Cliente <cliente@negocio.cl>\r\n"
    b"To: inbox@example.com\r\n"
    b"Subject: Re: propuesta\r\n"
    b"In-Reply-To: <m1@outreach.local>\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"\r\n"
    b"Quiero saber el precio\r\n"
)


def _settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_mode": "prod",
        "dry_run": False,
        "secret_key": "s" * 32,
        "database_url": "sqlite:///:memory:",
        "admin_email": "admin@example.com",
        "admin_password_hash": "hash-de-prueba",
        "agency_name": "Agencia Test",
        "agency_email": "agencia@example.com",
        "outreach_enabled": True,
        "outreach_smtp_host": "smtp.example",
        "outreach_smtp_port": 587,
        "outreach_smtp_user": "smtp-user",
        "outreach_smtp_password": "smtp-secret",
        "outreach_imap_host": "imap.example",
        "outreach_imap_user": "inbox@example.com",
        "outreach_imap_password": "imap-secret",
        "outreach_from": "Agencia <out@example.com>",
        "public_base_url": "https://agencia.example",
        "resend_api_key": "",
        "email_tx_from": "",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def _html_part(message: EmailMessage) -> str:
    for part in message.walk():
        if part.get_content_type() == "text/html":
            content = part.get_content()
            return content if isinstance(content, str) else str(content)
    return ""


def _assert_outreach_headers(message: EmailMessage) -> None:
    assert message["Reply-To"] == "inbox@example.com"
    assert message["From"] == "Agencia <out@example.com>"
    assert message["List-Unsubscribe"] == "<https://agencia.example/baja?mid=m1>"
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    html = _html_part(message)
    assert "<img" not in html.lower()
    assert "evil.test" not in html
    assert "pixel" not in html.lower()


class _Grab:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> str:
        self.messages.append(message)
        return "grabbed"


def _boom(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("smtp")


@pytest.mark.parametrize("factory", [FakeOutreach, SmtpOutreach])
@pytest.mark.parametrize(
    ("overrides", "kill", "reason"),
    [
        ({"dry_run": True}, True, "dry_run"),
        ({"app_mode": "demo", "dry_run": False}, True, "app_mode"),
        ({"outreach_enabled": False}, True, "outreach_disabled"),
        ({}, False, "kill_switch"),
        ({"outreach_smtp_password": ""}, True, "credential"),
    ],
)
def test_candado_no_abre_smtp(
    factory: type[FakeOutreach] | type[SmtpOutreach],
    overrides: dict[str, Any],
    kill: bool,
    reason: str,
    monkeypatch: pytest.MonkeyPatch,
    block_network: None,
) -> None:
    monkeypatch.setattr(smtplib, "SMTP", _boom)
    monkeypatch.setattr("integrations.email.outreach.smtplib.SMTP", _boom)
    mailer = factory(_settings(**overrides), kill_switch=kill)
    result = mailer.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML)
    assert result.status == "blocked"
    assert result.reason == reason
    if isinstance(mailer, FakeOutreach):
        assert mailer.outbox == []


def test_dry_run_outreach_no_llama_respx(
    monkeypatch: pytest.MonkeyPatch,
    respx_mock: Any,
    block_network: None,
) -> None:
    route = respx_mock.route().respond(200, json={"id": "no"})
    monkeypatch.setattr("integrations.email.outreach.smtplib.SMTP", _boom)
    settings = _settings(dry_run=True)
    fake = build_outreach_email(settings, kill_switch=True)
    real = SmtpOutreach(settings, kill_switch=True)
    assert isinstance(fake, FakeOutreach)
    assert fake.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML).status == "blocked"
    assert real.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML).status == "blocked"
    assert route.call_count == 0


def test_outreach_arma_baja_sin_pixel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("integrations.email.outreach.smtplib.SMTP", _boom)
    grab = _Grab()
    real = SmtpOutreach(_settings(), kill_switch=True, transport=grab)
    sent = real.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML)
    assert sent.status == "sent"
    assert grab.messages
    _assert_outreach_headers(grab.messages[0])

    fake = FakeOutreach(_settings(), kill_switch=True)
    assert fake.send("m1", "info@negocio.cl", "Hola", "Hola", _HTML).status == "sent"
    _assert_outreach_headers(fake.outbox[0])


def test_supresion_no_envia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("integrations.email.outreach.smtplib.SMTP", _boom)
    grab = _Grab()
    mailer = SmtpOutreach(
        _settings(),
        kill_switch=True,
        suppressed=lambda addr: addr.endswith("@no.cl"),
        transport=grab,
    )
    result = mailer.send("m1", "info@no.cl", "Hola", "Hola", "<p>Hola</p>")
    assert result.status == "blocked"
    assert result.reason == "suppressed"
    assert grab.messages == []


def test_fake_rebota_solo_si_la_simulacion_lo_pide() -> None:
    forced = FakeOutreach(_settings(), kill_switch=True, rng=random.Random(1), bounce_rate=1)
    assert forced.send("m1", "info@negocio.cl", "Hola", "Hola", "<p>Hola</p>").status == "bounced"
    assert forced.outbox == []

    quiet = FakeOutreach(_settings(), kill_switch=True, rng=random.Random(1), bounce_rate=0)
    assert quiet.send("m1", "info@negocio.cl", "Hola", "Hola", "<p>Hola</p>").status == "sent"

    rng = random.Random(0)
    probe = random.Random(0)
    expected = "bounced" if probe.random() < 0.03 else "sent"
    simulated = FakeOutreach(_settings(), kill_switch=True, rng=rng)
    assert simulated.send("m1", "info@negocio.cl", "Hola", "Hola", "<p>Hola</p>").status == expected


def test_fabrica_sin_credencial_o_demo_es_fake() -> None:
    missing = build_outreach_email(_settings(outreach_smtp_password=""), kill_switch=True)
    assert isinstance(missing, FakeOutreach)
    blocked = missing.send("m1", "info@negocio.cl", "Hola", "Hola", "<p>Hola</p>")
    assert blocked.reason == "credential"
    demo = build_outreach_email(_settings(app_mode="demo", dry_run=False), kill_switch=True)
    assert isinstance(demo, FakeOutreach)


def test_kill_switch_sale_de_settings_kv(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("integrations.email.outreach.smtplib.SMTP", _boom)
    engine = create_engine(f"sqlite:///{(tmp_path / 'mail.db').as_posix()}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    SettingsRepository(session).put("kill_switch", False, updated_by="test")
    session.flush()
    mailer = build_outreach_email(_settings(), session=session)
    assert isinstance(mailer, SmtpOutreach)
    blocked = mailer.send("m1", "info@negocio.cl", "Hola", "Hola", "<p>Hola</p>")
    assert blocked.status == "blocked"
    assert blocked.reason == "kill_switch"

    SettingsRepository(session).put("kill_switch", True, updated_by="test")
    session.flush()
    grab = _Grab()
    armed = build_outreach_email(_settings(), session=session, transport=grab)
    assert armed.send("m1", "info@negocio.cl", "Hola", "Hola", "<p>Hola</p>").status == "sent"
    assert grab.messages
    session.close()


@pytest.mark.parametrize(
    ("kwargs", "headers"),
    [
        ({"kind": "recibo"}, {}),
        ({"kind": "portal"}, {}),
        ({}, {"X-Mail-Kind": "derechos", "X-Entity": "1"}),
    ],
)
def test_transaccional_de_sistema_o_con_consentimiento(
    kwargs: dict[str, str],
    headers: dict[str, str],
    respx_mock: Any,
) -> None:
    route = respx_mock.post(RESEND_URL).respond(200, json={"id": "msg_1"})
    client = ResendTransactional(
        _settings(resend_api_key="re_test", email_tx_from="tx@example.com")
    )
    result = client.send(
        "cliente@negocio.cl",
        "Recibo",
        "Listo",
        "<p>Listo</p>",
        headers,
        consent=False,
        **kwargs,
    )
    assert result.status == "sent"
    assert result.provider_message_id == "msg_1"
    assert route.call_count == 1
    payload = route.calls.last.request.read()
    assert b"re_test" not in payload
    assert route.calls.last.request.headers["Authorization"] == "Bearer re_test"
    body = httpx.Response(200, content=payload).json()
    assert body["from"] == "tx@example.com"
    forwarded = body.get("headers") or {}
    assert "X-Mail-Kind" not in forwarded
    assert "x-mail-kind" not in {key.lower() for key in forwarded}


def test_transaccional_rechaza_sin_consentimiento(respx_mock: Any) -> None:
    route = respx_mock.post(RESEND_URL).respond(200, json={"id": "msg_1"})
    client = ResendTransactional(
        _settings(resend_api_key="re_test", email_tx_from="tx@example.com")
    )
    result = client.send(
        "a@b.cl",
        "Hola",
        "Hola",
        "<p>Hola</p>",
        {},
        consent=False,
        kind="marketing",
    )
    assert result.status == "rejected"
    assert result.reason == "sin_consentimiento"
    assert route.call_count == 0

    allowed = client.send("a@b.cl", "Hola", "Hola", "<p>Hola</p>", {}, consent=True)
    assert allowed.status == "sent"
    assert route.call_count == 1


def test_transaccional_dry_run_no_llama_respx(respx_mock: Any) -> None:
    route = respx_mock.post(RESEND_URL).respond(200, json={"id": "msg_1"})
    client = ResendTransactional(
        _settings(dry_run=True, resend_api_key="re_test", email_tx_from="tx@example.com")
    )
    blocked = client.send("a@b.cl", "Hola", "Hola", "<p>Hola</p>", {}, consent=True)
    assert blocked.status == "blocked"
    assert route.call_count == 0


def test_fabrica_transaccional_demo_no_abre_red(respx_mock: Any) -> None:
    route = respx_mock.route().respond(200, json={"id": "no"})
    fake = build_transactional_email(
        _settings(
            app_mode="demo",
            dry_run=True,
            resend_api_key="re_test",
            email_tx_from="tx@example.com",
        )
    )
    assert isinstance(fake, FakeTransactional)
    rejected = fake.send("a@b.cl", "Hola", "Hola", "<p>Hola</p>", {}, consent=False)
    assert rejected.status == "rejected"
    assert fake.send("a@b.cl", "Hola", "Hola", "<p>Hola</p>", {}, consent=True).status == "sent"
    assert route.call_count == 0


def test_imap_real_no_abre_socket_y_parsea(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _FakeSSL:
        def __init__(self, host: str, port: int) -> None:
            calls.append(f"connect:{host}:{port}")

        def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
            assert user == "inbox@example.com"
            assert password == "imap-secret"
            return "OK", []

        def select(self, mailbox: str) -> tuple[str, list[bytes]]:
            assert mailbox == "INBOX"
            return "OK", [b"1"]

        def search(self, charset: object, criteria: str) -> tuple[str, list[bytes]]:
            assert criteria == "UNSEEN"
            return "OK", [b"7"]

        def fetch(self, uid: bytes, spec: str) -> tuple[str, list[tuple[bytes, bytes]]]:
            assert uid == b"7"
            assert spec == "(RFC822)"
            return "OK", [(b"7 (RFC822)", _RAW)]

        def logout(self) -> tuple[str, list[bytes]]:
            calls.append("logout")
            return "OK", []

    monkeypatch.setattr("integrations.email.inbound.imaplib.IMAP4_SSL", _FakeSSL)
    polled = ImapPoller(_settings()).poll()
    assert calls == ["connect:imap.example:993", "logout"]
    assert polled[0].from_addr.startswith("Cliente")
    assert polled[0].text == "Quiero saber el precio"
    assert polled[0].in_reply_to == "<m1@outreach.local>"

    dry = ImapPoller(_settings(dry_run=True))
    assert dry.poll() == []
    assert dry.connects == 0
    assert calls == ["connect:imap.example:993", "logout"]


def test_fabrica_imap_demo_es_fake() -> None:
    fake = build_inbound_poller(_settings(app_mode="demo", dry_run=True))
    assert isinstance(fake, FakeInbound)
    fake.enqueue(
        InboundMail(
            message_id="<a>",
            from_addr="a@b.cl",
            to_addr="inbox@example.com",
            subject="Hola",
            text="hola",
        )
    )
    assert len(fake.poll()) == 1
    assert fake.poll() == []
    prod = build_inbound_poller(_settings())
    assert isinstance(prod, ImapPoller)
