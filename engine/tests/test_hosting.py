"""Caddy copia el sitio y el dominio solo vale si el proyecto está aprobado o publicado."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.config import Settings
from db.models import Base, Lead, Order, Project
from integrations.hosting import (
    CaddyHosting,
    CloudflarePagesHosting,
    FakeHosting,
    build_hosting,
)
from integrations.hosting.base import CF_API
from integrations.storage import FakeStorage, LocalStorage, build_storage


def _settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_mode": "prod",
        "dry_run": False,
        "secret_key": "s" * 32,
        "database_url": "sqlite:///:memory:",
        "admin_email": "admin@example.com",
        "admin_password_hash": "hash-de-prueba",
        "public_base_url": "https://agencia.example",
        "agency_name": "Agencia Test",
        "agency_email": "agencia@example.com",
        "hosting_provider": "caddy",
        "client_sites_dir": "engine/output/clients",
        "cloudflare_api_token": "",
        "cloudflare_account_id": "",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def _site(root: Path) -> Path:
    root.mkdir()
    (root / "index.html").write_text("<p>hola</p>", encoding="utf-8")
    (root / "css").mkdir()
    (root / "css" / "site.css").write_text("body{}", encoding="utf-8")
    return root


def test_caddy_copia_al_slug_y_rechaza_dominio(tmp_path: Path) -> None:
    files = _site(tmp_path / "src")
    sites = tmp_path / "clients"
    hosting = CaddyHosting(sites, allowed_domains={"cliente.cl"})
    assert hosting.domain_allowed("www.Cliente.cl") is True
    assert hosting.domain_allowed("otro.cl") is False
    assert hosting.domain_allowed("") is False
    dest = Path(hosting.publish("Proyecto_1", files, "cliente.cl"))
    assert dest == (sites / "proyecto_1").resolve()
    assert (dest / "index.html").read_text(encoding="utf-8") == "<p>hola</p>"
    assert (dest / "css" / "site.css").read_text(encoding="utf-8") == "body{}"
    with pytest.raises(ValueError, match="dominio"):
        hosting.publish("Proyecto_1", files, "otro.cl")
    with pytest.raises(ValueError, match="publicable"):
        hosting.publish("../secreto", files, None)
    assert not (sites / "secreto").exists()


def test_dominio_por_sesion_solo_aprobado_o_publicado(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'sites.db').as_posix()}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    lead = Lead(
        source="inbound_contacto",
        business="Café Andes",
        category="cafeteria",
        city="Santiago",
        commune="Providencia",
        opportunity_score=70,
        status="pagado",
        estimated_value_clp=250_000,
        tone="tu",
    )
    session.add(lead)
    session.flush()
    paid = Order(
        lead_id=lead.id,
        package_code="landing_esencial",
        amount_clp=250_000,
        iva_clp=0,
        total_clp=250_000,
        deposit_percent=50,
        status="paid",
    )
    pending = Order(
        lead_id=lead.id,
        package_code="landing_pro",
        amount_clp=350_000,
        iva_clp=0,
        total_clp=350_000,
        deposit_percent=50,
        status="pending",
    )
    session.add_all([paid, pending])
    session.flush()
    session.add_all(
        [
            Project(
                order_id=paid.id,
                lead_id=lead.id,
                status="aprobado",
                max_revisions=1,
                domain="Cliente.cl",
            ),
            Project(
                order_id=pending.id,
                lead_id=lead.id,
                status="en_produccion",
                max_revisions=2,
                domain="otro.cl",
            ),
        ]
    )
    session.flush()
    hosting = CaddyHosting(tmp_path / "clients", session=session)
    assert hosting.domain_allowed("www.cliente.cl") is True
    assert hosting.domain_allowed("otro.cl") is False
    assert hosting.domain_allowed("nadie.cl") is False
    session.close()


def test_fabrica_hosting_y_cloudflare(tmp_path: Path, respx_mock: Any) -> None:
    files = _site(tmp_path / "src")
    demo = build_hosting(_settings(app_mode="demo", dry_run=True), allowed_domains={"cliente.cl"})
    assert isinstance(demo, FakeHosting)
    assert demo.publish("abc", files, "cliente.cl") == "fake://sites/abc"
    assert demo.domain_allowed("cliente.cl") is True
    with pytest.raises(ValueError):
        demo.publish("abc", files, "otro.cl")

    caddy = build_hosting(
        _settings(client_sites_dir=str(tmp_path / "publicado")),
        allowed_domains={"cliente.cl"},
    )
    assert isinstance(caddy, CaddyHosting)
    published = Path(caddy.publish("abc", files, None))
    assert published.is_dir()
    assert (published / "index.html").is_file()

    route = respx_mock.post(f"{CF_API}/accounts/acc-1/pages/projects/abc/deployments").respond(
        201, json={"success": True, "result": {"url": "https://abc.pages.dev"}}
    )
    remote = build_hosting(
        _settings(
            hosting_provider="cloudflare_pages",
            cloudflare_api_token="cf-test",
            cloudflare_account_id="acc-1",
        ),
        allowed_domains={"cliente.cl"},
    )
    assert isinstance(remote, CloudflarePagesHosting)
    assert remote.publish("abc", files, "cliente.cl") == "https://abc.pages.dev"
    assert route.calls.last.request.headers["Authorization"] == "Bearer cf-test"
    with pytest.raises(ValueError):
        remote.publish("abc", files, "otro.cl")
    assert route.call_count == 1
    missing = build_hosting(_settings(hosting_provider="cloudflare_pages"))
    assert isinstance(missing, FakeHosting)


def test_storage_local_y_fake(tmp_path: Path) -> None:
    local = LocalStorage(tmp_path / "output")
    stored = local.put("artefactos/a.txt", b"hola", content_type="text/plain")
    assert Path(stored).read_bytes() == b"hola"
    assert local.get("artefactos/a.txt") == b"hola"
    with pytest.raises(ValueError):
        local.put("../secreto.txt", b"no")
    assert not (tmp_path / "secreto.txt").exists()

    fake = FakeStorage()
    assert fake.put("artefactos/a.txt", b"hola") == "fake://artefactos/a.txt"
    assert fake.get("artefactos/a.txt") == b"hola"
    with pytest.raises(ValueError):
        fake.put("../x", b"no")
    assert isinstance(build_storage(_settings(app_mode="demo", dry_run=True)), FakeStorage)
    prod = build_storage(_settings(), root=tmp_path / "prod")
    assert isinstance(prod, LocalStorage)
    assert prod.put("b.txt", b"ok")
    assert prod.get("b.txt") == b"ok"
