"""Places, auditor y video sin red real. respx cubre el HTTP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from agents.catalog import DEMO_HIGH_VALUE_CATEGORIES
from agents.context import AgentContext
from agents.scout import ScoutAgent
from core.config import get_settings, reset_settings
from db.repositories import LeadRepository
from db.session import create_all, reset_engine, session_scope
from integrations.pagespeed.base import FakeWebAuditor, HttpWebAuditor, build_auditor
from integrations.places.base import (
    DemoSource,
    GooglePlacesSource,
    PlaceHit,
    accepts,
    build_places,
)
from integrations.places.chains import is_chain
from integrations.video.base import Shot, Storyboard, StoryboardRenderer, build_video

_PLACES = "https://places.googleapis.com/v1/places:searchText"
_MASK = ",".join(
    (
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.types",
        "places.googleMapsUri",
        "places.nationalPhoneNumber",
    )
)


@pytest.fixture(autouse=True)
def _caches() -> Any:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("OUTREACH_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'int.db').as_posix()}")
    monkeypatch.setenv("AGENCY_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setenv("GROK_API_KEY", "")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "")
    monkeypatch.setenv("PAGESPEED_API_KEY", "")
    monkeypatch.setenv("SCOUT_COMMUNES", "Providencia")
    monkeypatch.setenv("SCOUT_CATEGORIES", "peluqueria")
    reset_settings()
    reset_engine()
    create_all()
    return tmp_path


def _place(
    place_id: str,
    name: str,
    *,
    status: str = "OPERATIONAL",
    rating: float = 4.6,
    reviews: int = 30,
) -> dict[str, Any]:
    return {
        "id": place_id,
        "displayName": {"text": name},
        "formattedAddress": "Ñuñoa, Chile",
        "rating": rating,
        "userRatingCount": reviews,
        "businessStatus": status,
        "types": ["store"],
        "googleMapsUri": "https://maps.example/lugar",
    }


def test_demo_source_no_abre_socket_ni_inventa_correo(block_network: None) -> None:
    hits = DemoSource(seed=42).search("Ñuñoa", "peluqueria", 3)
    assert hits
    assert all(hit.national_phone_number is None for hit in hits)
    assert all(item.rating is not None and item.rating >= 4 for item in hits)
    dumped = " ".join(hit.model_dump_json() for hit in hits)
    assert "@" not in dumped


def test_google_places_filtra_y_pide_field_mask(block_network: None) -> None:
    payload = {
        "places": [
            _place("c1", "Falabella Ñuñoa"),
            _place("c2", "Peluquería Cerrada", status="CLOSED_TEMPORARILY"),
            _place("c3", "Peluquería Baja", rating=3.2),
            _place("c4", "Peluquería Nueva", reviews=3),
            _place("ok", "Peluquería Las Palmas"),
        ]
    }
    with respx.mock:
        route = respx.post(_PLACES).mock(return_value=httpx.Response(200, json=payload))
        hits = GooglePlacesSource("test-key", min_rating=4.0, min_reviews=15).search(
            "Ñuñoa",
            "peluqueria",
            5,
        )
    assert [hit.name for hit in hits] == ["Peluquería Las Palmas"]
    request = route.calls[0].request
    assert request.headers["X-Goog-FieldMask"] == _MASK
    body = json.loads(request.content)
    assert body["languageCode"] == "es"
    assert body["regionCode"] == "CL"
    assert "Ñuñoa" in body["textQuery"]
    assert "Peluquería" in body["textQuery"]


def test_cadenas_y_accepts() -> None:
    assert is_chain("Starbucks Providencia")
    assert is_chain("Farmacias Ahumada")
    assert not is_chain("Café del Barrio")
    assert not is_chain("Óptica París Local")
    closed = PlaceHit(
        place_id="x",
        name="Café del Barrio",
        formatted_address="Santiago",
        rating=4.8,
        user_rating_count=40,
        business_status="CLOSED_TEMPORARILY",
    )
    assert accepts(closed, min_rating=4, min_reviews=15) is False


def test_build_places_en_demo_es_fake(db: Path, block_network: None) -> None:
    assert isinstance(build_places(get_settings()), DemoSource)
    audit = build_auditor(get_settings()).audit("https://demo.invalid/negocio")
    assert audit.contact_email is None
    assert audit.opportunity_score == 62


def test_fake_auditor_sin_url_sube_el_score(block_network: None) -> None:
    audit = FakeWebAuditor().audit(None)
    assert 80 <= audit.opportunity_score <= 95
    assert audit.contact_email is None
    assert audit.source_url is None


def test_auditor_no_adivina_email_y_respeta_robots(block_network: None) -> None:
    home = """
    <html><head><meta name="viewport" content="width=device-width"></head>
    <body>
      <p>Escriba a secreto@negocio.cl hoy mismo.</p>
      <a href="mailto:publico@negocio.cl">correo</a>
      <a href="https://instagram.com/negocio.local">ig</a>
      <a href="/roto">roto</a>
      Copyright 2018
    </body></html>
    """
    with respx.mock:
        respx.get("https://negocio.cl/robots.txt").mock(return_value=httpx.Response(404))
        respx.get("https://negocio.cl/").mock(return_value=httpx.Response(200, text=home))
        respx.get("https://negocio.cl/roto").mock(return_value=httpx.Response(404))
        audit = HttpWebAuditor(
            user_agent="AgenciaBot/1.0 (+http://localhost)",
            min_interval=0,
        ).audit("https://negocio.cl/")
    assert audit.contact_email == "publico@negocio.cl"
    assert audit.contact_email_source_url == "https://negocio.cl/"
    assert "secreto@negocio.cl" not in (audit.contact_email or "")
    assert audit.instagram_handle == "negocio.local"
    assert audit.source_url == "https://negocio.cl/"
    assert "https://negocio.cl/roto" in audit.broken_links
    assert audit.copyright_year == 2018
    assert audit.has_viewport is True

    blocked = """
    <html><body><a href="mailto:no@negocio.cl">m</a></body></html>
    """
    with respx.mock:
        respx.get("https://cerrado.cl/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        )
        respx.get("https://cerrado.cl/").mock(return_value=httpx.Response(200, text=blocked))
        denied = HttpWebAuditor(
            user_agent="AgenciaBot/1.0 (+http://localhost)", min_interval=0
        ).audit("https://cerrado.cl/")
    assert denied.contact_email is None
    assert any("robots" in note for note in denied.notes)


def test_pagespeed_opcional(block_network: None) -> None:
    home = (
        "<html><head><meta name='viewport' content='width=device-width'></head><body></body></html>"
    )
    speed = {"lighthouseResult": {"categories": {"performance": {"score": 0.42}}}}
    with respx.mock:
        respx.get("https://rapido.cl/robots.txt").mock(return_value=httpx.Response(404))
        respx.get("https://rapido.cl/").mock(return_value=httpx.Response(200, text=home))
        route = respx.get(url__startswith="https://www.googleapis.com/pagespeedonline/").mock(
            return_value=httpx.Response(200, json=speed)
        )
        audit = HttpWebAuditor(
            user_agent="AgenciaBot/1.0 (+http://localhost)",
            pagespeed_key="ps-key",
            min_interval=0,
        ).audit("https://rapido.cl/")
    assert audit.pagespeed_score == 42
    assert "strategy=mobile" in str(route.calls[0].request.url)


def test_storyboard_sin_binarios(tmp_path: Path) -> None:
    notes: list[str] = []
    board = Storyboard(
        title="Café Andes",
        duration_s=12,
        voiceover="Una página clara.",
        shots=[Shot(start_s=0, end_s=3, visual="Fachada", on_screen="Café Andes")],
    )
    landing = tmp_path / "cafe.html"
    landing.write_text("<html></html>", encoding="utf-8")
    result = StoryboardRenderer(tmp_path, on_info=notes.append).render(landing, board)
    assert result.kind == "storyboard"
    assert Path(result.path).name.startswith("storyboard_")
    assert Path(result.path).is_file()
    assert notes
    settings = get_settings()
    renderer = build_video(settings, output_dir=tmp_path)
    assert isinstance(renderer, StoryboardRenderer)


def test_alto_valor_forzado_solo_en_demo_y_rubro(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCOUT_CATEGORIES", "peluqueria")
    monkeypatch.setenv("APP_MODE", "demo")
    reset_settings()
    with session_scope() as session:
        result = ScoutAgent(source=DemoSource(), auditor=FakeWebAuditor()).run(
            AgentContext(session, count=1, force_high_value=True)
        )
        lead = LeadRepository(session).get(result.output["ids"][0])
        assert lead is not None
        assert lead.category == "peluqueria"
        assert lead.high_value is False
        assert lead.estimated_value_clp < 1_000_000
        assert lead.contact_email is None

    monkeypatch.setenv("APP_MODE", "prod")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("SCOUT_CATEGORIES", "clinica-dental")
    reset_settings()
    reset_engine()
    create_all()
    with session_scope() as session:
        result = ScoutAgent(source=DemoSource(), auditor=FakeWebAuditor()).run(
            AgentContext(session, count=1, force_high_value=True)
        )
        lead = LeadRepository(session).get(result.output["ids"][0])
        assert lead is not None
        assert lead.category == "clinica-dental"
        assert lead.high_value is False
        assert lead.estimated_value_clp <= 450_000

    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("SCOUT_COMMUNES", "Las Condes")
    reset_settings()
    reset_engine()
    create_all()
    with session_scope() as session:
        result = ScoutAgent(source=DemoSource(), auditor=FakeWebAuditor()).run(
            AgentContext(session, count=1, force_high_value=True)
        )
        lead = LeadRepository(session).get(result.output["ids"][0])
        assert lead is not None
        assert lead.category in DEMO_HIGH_VALUE_CATEGORIES
        assert lead.high_value is True
        assert lead.estimated_value_clp == get_settings().hitl_value_clp


def test_multi_sede_es_alto_valor_aunque_sea_peluqueria(db: Path) -> None:
    class _Source:
        def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]:
            return [
                PlaceHit(
                    place_id="multi-1",
                    name="Peluquería Las Palmas multi sede",
                    formatted_address="Providencia, Chile",
                    rating=4.7,
                    user_rating_count=22,
                    business_status="OPERATIONAL",
                )
            ]

    with session_scope() as session:
        result = ScoutAgent(source=_Source(), auditor=FakeWebAuditor()).run(
            AgentContext(session, count=1, force_high_value=False)
        )
        lead = LeadRepository(session).get(result.output["ids"][0])
        assert lead is not None
        assert lead.high_value is True
        assert lead.estimated_value_clp == get_settings().hitl_value_clp
