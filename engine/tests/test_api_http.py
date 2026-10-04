"""API HTTP contra sqlite temporal. No usa engine/state/agencia.db."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api.app import create_app
from api.deps import LocalPaymentProvider, PaymentFact
from api.security import hash_password, mercadopago_signature, reset_login_attempts
from core.config import reset_settings
from core.states import transition
from db.models import (
    Approval,
    Artifact,
    Event,
    Lead,
    LlmCall,
    Message,
    Order,
    Payment,
    User,
)
from db.repositories import EventRepository, LeadRepository, MessageRepository, SettingsRepository
from db.session import reset_engine, session_scope

_EMAIL = "admin@example.com"
_PASSWORD = "clave-de-prueba"
_PASSWORD_HASH = hash_password(_PASSWORD)
_MP_SECRET = "mp-test-secret"

_PATHS = {
    "/healthz",
    "/readyz",
    "/api/public/paquetes",
    "/api/public/diagnostico",
    "/api/public/contacto",
    "/api/public/checkout",
    "/api/public/baja",
    "/u/{token}",
    "/api/public/derechos",
    "/demo/{token}",
    "/api/public/proyecto/{token}",
    "/api/public/proyecto/{token}/intake",
    "/api/public/proyecto/{token}/feedback",
    "/api/public/proyecto/{token}/aprobar",
    "/api/internal/domain-check",
    "/webhooks/mercadopago",
    "/webhooks/calcom",
    "/webhooks/calendly",
    "/webhooks/email",
    "/webhooks/meta",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/leads",
    "/api/leads/{id}",
    "/api/approvals",
    "/api/approvals/{id}/approve",
    "/api/approvals/{id}/reject",
    "/api/approvals/{id}/edit",
    "/api/messages",
    "/api/manual-queue",
    "/api/manual-queue/{id}/mark-sent",
    "/api/conversations",
    "/api/conversations/{id}/reply",
    "/api/agents",
    "/api/actions/{name}",
    "/api/events",
    "/api/events/stream",
    "/api/metrics",
    "/api/orders",
    "/api/projects",
    "/api/projects/{id}",
    "/api/settings",
    "/api/compliance/suppression",
    "/api/compliance/data-requests",
    "/api/meta/categories",
    "/api/meta/statuses",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    db_path = tmp_path / "api.db"
    url = f"sqlite:///{db_path.as_posix()}"
    assert "state/agencia.db" not in url
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("OUTREACH_ENABLED", "false")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_EMAIL", _EMAIL)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost")
    monkeypatch.setenv("MP_WEBHOOK_SECRET", _MP_SECRET)
    monkeypatch.setenv("CALCOM_WEBHOOK_SECRET", "cal-test-secret")
    monkeypatch.setenv("CALENDLY_WEBHOOK_SIGNING_KEY", "calendly-test-secret")
    monkeypatch.setenv("META_APP_SECRET", "meta-test-secret")
    monkeypatch.setenv("META_VERIFY_TOKEN", "meta-verify")
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "whsec-test")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8080")
    reset_settings()
    reset_engine()
    reset_login_attempts()
    app = create_app()
    with TestClient(app) as test_client:
        with session_scope() as session:
            session.add(User(email=_EMAIL, password_hash=_PASSWORD_HASH))
        test_client.db_url = url  # type: ignore[attr-defined]
        yield test_client
    reset_engine()
    reset_settings()
    reset_login_attempts()


def _diag(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "business": "Café Sur",
        "email": "persona@example.com",
        "commune": "Ñuñoa",
        "category": "cafeteria",
        "consent": True,
        "consent_text": "Acepto el tratamiento para el diagnóstico gratuito.",
        "website_url": None,
        "honeypot": "",
        "turnstile_token": "",
    }
    payload.update(overrides)
    return payload


def _login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": _EMAIL, "password": _PASSWORD})
    assert response.status_code == 200, response.text
    token = client.cookies.get("csrf_token")
    assert token
    return {"X-CSRF-Token": token}


def _lead(session: Any, **overrides: Any) -> Lead:
    data: dict[str, Any] = {
        "source": "outbound_demo",
        "business": "Taller Sur",
        "category": "taller-mecanico",
        "city": "Santiago",
        "commune": "Providencia",
        "opportunity_score": 70,
        "status": "nuevo",
        "estimated_value_clp": 250_000,
        "high_value": False,
        "tone": "tu",
    }
    data.update(overrides)
    return LeadRepository(session).add(Lead(**data))


def _lead_count() -> int:
    with session_scope() as session:
        return int(session.scalar(select(func.count()).select_from(Lead)) or 0)


def _mp_headers(payment_id: str) -> dict[str, str]:
    signature = mercadopago_signature(_MP_SECRET, payment_id, "req-1", "1700000000")
    return {
        "x-signature": signature,
        "x-request-id": "req-1",
        "content-type": "application/json",
    }


def test_openapi_tiene_los_paths_de_f0(client: TestClient) -> None:
    paths = set(client.app.openapi()["paths"])
    assert _PATHS - paths == set()


def test_health_y_ready(client: TestClient) -> None:
    health = client.get("/healthz")
    ready = client.get("/readyz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"
    paquetes = client.get("/api/public/paquetes")
    assert paquetes.status_code == 200
    assert len(paquetes.json()) == 4


def test_readyz_503_si_la_base_falla(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    original = client.db_url  # type: ignore[attr-defined]
    bad = tmp_path / "sin-directorio" / "no.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{bad.as_posix()}")
    reset_settings()
    reset_engine()
    try:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_ready"
    finally:
        monkeypatch.setenv("DATABASE_URL", original)
        reset_settings()
        reset_engine()


def test_login_cookie_y_csrf(client: TestClient) -> None:
    anonymous = client.get("/api/auth/me")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "unauthenticated"
    denied = client.put("/api/settings", json={"kill_switch": True})
    assert denied.status_code == 401

    login = client.post("/api/auth/login", json={"email": _EMAIL, "password": "no-es"})
    assert login.status_code == 401
    assert login.json()["error"]["code"] == "invalid_credentials"

    ok = client.post("/api/auth/login", json={"email": _EMAIL, "password": _PASSWORD})
    assert ok.status_code == 200
    assert ok.json() == {"email": _EMAIL}
    cookies = ok.headers.get_list("set-cookie")
    session_cookie = next(item for item in cookies if item.lower().startswith("session="))
    csrf_cookie = next(item for item in cookies if item.lower().startswith("csrf_token="))
    assert "httponly" in session_cookie.lower()
    assert "samesite=lax" in session_cookie.lower()
    assert "secure" not in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == _EMAIL

    missing = client.put("/api/settings", json={"kill_switch": False})
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_invalid"

    headers = {"X-CSRF-Token": client.cookies.get("csrf_token")}
    saved = client.put(
        "/api/settings",
        json={"kill_switch": False, "app_mode": "prod"},
        headers=headers,
    )
    assert saved.status_code == 200
    logged_out = client.post("/api/auth/logout", headers=headers)
    assert logged_out.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limit(client: TestClient) -> None:
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": _EMAIL, "password": "mala"},
        )
        assert response.status_code == 401
    blocked = client.post("/api/auth/login", json={"email": _EMAIL, "password": "mala"})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"


def test_diagnostico_con_consentimiento_crea_lead(client: TestClient) -> None:
    response = client.post("/api/public/diagnostico", json=_diag())
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "diagnosticado"
    with session_scope() as session:
        lead = session.get(Lead, body["id"])
        assert lead is not None
        assert lead.status == "diagnosticado"
        assert lead.source == "inbound_diagnostico"
        assert lead.contact_email == "persona@example.com"
        assert isinstance(lead.consent, dict)
        assert lead.consent["type"] == "diagnostico"
        assert lead.consent["text_version"]
        assert lead.consent["ip_hash"]
        assert "testclient" not in lead.consent["ip_hash"]


def test_diagnostico_sin_consentimiento_es_422(client: TestClient) -> None:
    response = client.post("/api/public/diagnostico", json=_diag(consent=False))
    assert response.status_code == 422
    assert "error" in response.json()
    assert _lead_count() == 0


def test_honeypot_no_crea_lead(client: TestClient) -> None:
    diag = client.post("/api/public/diagnostico", json=_diag(honeypot="http://spam"))
    contact = client.post(
        "/api/public/contacto",
        json={
            "name": "Ana",
            "email": "ana@example.com",
            "message": "hola",
            "consent": True,
            "honeypot": "llena",
        },
    )
    assert diag.status_code == 202
    assert contact.status_code == 202
    assert _lead_count() == 0


def test_turnstile_rechaza_token_invalido(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "secreto-turnstile")
    reset_settings()
    url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    with respx.mock(assert_all_called=True) as router:
        route = router.post(url).mock(return_value=httpx.Response(200, json={"success": False}))
        response = client.post(
            "/api/public/diagnostico",
            json=_diag(turnstile_token="token-falso"),
        )
        assert response.status_code == 403
        assert route.called
    assert _lead_count() == 0


def test_turnstile_prod_sin_secret_rechaza(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_MODE", "prod")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "")
    reset_settings()
    response = client.post("/api/public/diagnostico", json=_diag())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "turnstile_rejected"
    assert _lead_count() == 0


def test_webhook_firma_invalida_es_401(client: TestClient) -> None:
    response = client.post(
        "/webhooks/mercadopago",
        content=b'{"data":{"id":"1"},"transaction_amount":999999}',
        headers={
            "x-signature": "ts=1,v1=deadbeef",
            "x-request-id": "req",
            "content-type": "application/json",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_signature"
    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(Payment)) == 0


@pytest.mark.parametrize(
    "path",
    ["/webhooks/calcom", "/webhooks/calendly", "/webhooks/email", "/webhooks/meta"],
)
def test_otros_webhooks_rechazan_firma(client: TestClient, path: str) -> None:
    response = client.post(path, content=b"{}", headers={"content-type": "application/json"})
    assert response.status_code == 401


def test_pago_duplicado_no_duplica_payment_ni_order(client: TestClient) -> None:
    with session_scope() as session:
        lead = _lead(session, business="Café Pago")
        lead_id = lead.id
    provider = client.app.state.payment_provider
    assert isinstance(provider, LocalPaymentProvider)
    provider.remember(
        PaymentFact(
            provider_payment_id="pay-1",
            status="approved",
            amount_clp=250_000,
            lead_id=lead_id,
            package_code="landing_esencial",
            raw={"source": "fake"},
        )
    )
    body = b'{"data":{"id":"pay-1"},"status":"rejected","transaction_amount":1}'
    headers = _mp_headers("pay-1")
    first = client.post("/webhooks/mercadopago", content=body, headers=headers)
    second = client.post("/webhooks/mercadopago", content=body, headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["duplicate"] is True
    with session_scope() as session:
        payments = list(session.scalars(select(Payment)))
        orders = list(session.scalars(select(Order)))
        assert len(payments) == 1
        assert len(orders) == 1
        assert payments[0].provider_payment_id == "pay-1"
        assert payments[0].amount_clp == 250_000
        assert payments[0].status == "approved"
        assert orders[0].lead_id == lead_id


def test_aprobar_hitl_vuelve_a_paused_from(client: TestClient) -> None:
    headers = _login(client)
    with session_scope() as session:
        lead = _lead(session, status="enviado", business="Óptica Norte")
        transition(session, lead, "revision", actor="humano", reason="revisar deal")
        approval = Approval(
            lead_id=lead.id,
            kind="deal_alto_valor",
            payload={},
            status="pending",
        )
        session.add(approval)
        session.flush()
        approval_id = approval.id
        assert lead.paused_from == "enviado"
    response = client.post(f"/api/approvals/{approval_id}/approve", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "enviado"
    assert response.json()["paused_from"] is None
    with session_scope() as session:
        stored = session.get(Lead, response.json()["id"])
        assert stored is not None
        assert stored.status == "enviado"
        assert stored.paused_from is None
        row = session.get(Approval, approval_id)
        assert row is not None
        assert row.status == "approved"


def test_editar_deja_el_mensaje_en_checking(client: TestClient) -> None:
    headers = _login(client)
    with session_scope() as session:
        lead = _lead(session, status="revision", paused_from="pitch_listo", business="Spa Luz")
        message = MessageRepository(session).add(
            Message(
                lead_id=lead.id,
                thread_id=lead.id,
                direction="out",
                channel="email_outreach",
                status="approved",
                subject="Hola",
                body_text="texto original",
            )
        )
        approval = Approval(
            lead_id=lead.id,
            kind="compliance",
            payload={"message_id": message.id},
            status="pending",
        )
        session.add(approval)
        session.flush()
        approval_id = approval.id
        message_id = message.id
    response = client.post(
        f"/api/approvals/{approval_id}/edit",
        json={"body_text": "texto editado", "subject": "Nuevo asunto"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    with session_scope() as session:
        message = session.get(Message, message_id)
        approval = session.get(Approval, approval_id)
        lead = session.scalar(select(Lead))
        assert message is not None
        assert message.status == "checking"
        assert message.body_text == "texto editado"
        assert message.subject == "Nuevo asunto"
        assert message.sent_at is None
        assert approval is not None
        assert approval.status == "edited"
        assert lead is not None
        assert lead.status == "revision"


def test_kill_switch_persiste_y_app_mode_es_de_solo_lectura(client: TestClient) -> None:
    headers = _login(client)
    saved = client.put(
        "/api/settings",
        json={"kill_switch": True, "app_mode": "prod", "quotas": {"scout_daily_limit": 3}},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["kill_switch"] is True
    assert saved.json()["app_mode"] == "demo"
    with session_scope() as session:
        assert SettingsRepository(session).get("kill_switch") is True
    again = client.get("/api/settings")
    assert again.json()["kill_switch"] is True
    assert again.json()["app_mode"] == "demo"
    assert again.json()["quotas"]["scout_daily_limit"] == 3


def test_metrics_salen_de_la_base(client: TestClient) -> None:
    _login(client)
    before = client.get("/api/metrics")
    assert before.status_code == 200
    assert before.json()["revenue_clp"] == 0
    assert before.json()["llm_cost_usd"] == 0
    assert before.json()["tokens_today"] == 0
    with session_scope() as session:
        lead = _lead(session, business="Métricas")
        order = Order(
            lead_id=lead.id,
            package_code="landing_esencial",
            amount_clp=1000,
            iva_clp=190,
            total_clp=1190,
            deposit_percent=50,
            status="pending",
        )
        session.add(order)
        session.flush()
        session.add(
            Payment(
                order_id=order.id,
                provider="mercadopago",
                provider_payment_id="p-ok",
                status="approved",
                amount_clp=1190,
                raw={},
            )
        )
        session.add(
            Payment(
                order_id=order.id,
                provider="mercadopago",
                provider_payment_id="p-no",
                status="pending",
                amount_clp=5000,
                raw={},
            )
        )
        session.add(
            LlmCall(
                agent="diagnoser",
                model="grok-4.7",
                prompt_name="diagnoser",
                prompt_version="0",
                tokens_in=20,
                tokens_out=10,
                cost_usd=Decimal("0.40"),
                latency_ms=5,
                ok=True,
                lead_id=lead.id,
            )
        )
    after = client.get("/api/metrics").json()
    assert after["revenue_clp"] == 1190
    assert after["llm_cost_usd"] == pytest.approx(0.4)
    assert after["tokens_today"] == 30
    assert after["funnel"]["nuevo"] == 1


def test_demo_html_y_expirada(client: TestClient, tmp_path: Any) -> None:
    html_path = tmp_path / "demo.html"
    html_path.write_text("<html><body>demo viva</body></html>", encoding="utf-8")
    with session_scope() as session:
        session.add(
            Artifact(
                kind="landing_demo",
                version=1,
                path=str(html_path),
                public_token="viva",
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        session.add(
            Artifact(
                kind="landing_demo",
                version=1,
                path=str(html_path),
                public_token="vieja",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
    live = client.get("/demo/viva")
    assert live.status_code == 200
    assert live.headers["x-robots-tag"] == "noindex, nofollow"
    assert "demo viva" in live.text
    dead = client.get("/demo/vieja")
    assert dead.status_code == 410
    assert dead.headers["x-robots-tag"] == "noindex, nofollow"


def test_sse_emite_y_cierra(client: TestClient) -> None:
    _login(client)
    with session_scope() as session:
        EventRepository(session).append(agent="api", level="info", message="hola-sse")
    response = client.get("/api/events/stream")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.text.startswith(":")
    assert "hola-sse" in response.text
    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1


def test_rutas_admin_de_lectura(client: TestClient) -> None:
    _login(client)
    assert client.get("/api/leads").status_code == 200
    assert client.get("/api/agents").status_code == 200
    assert len(client.get("/api/meta/categories").json()) == 15
    statuses = client.get("/api/meta/statuses").json()
    assert "paused_from" in statuses["transitions"]["revision"]
    assert client.get("/api/orders").status_code == 200
    assert client.get("/api/events").status_code == 200
