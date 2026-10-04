"""La configuración sale del entorno, con alias y archivos .env en el orden del contrato."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import AliasChoices

from core.config import Settings, get_settings, reset_settings
from core.hitl import needs_value_review


@pytest.fixture(autouse=True)
def _caches() -> object:
    reset_settings()
    yield
    reset_settings()


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, field in Settings.model_fields.items():
        monkeypatch.delenv(name.upper(), raising=False)
        alias = field.validation_alias
        if isinstance(alias, AliasChoices):
            for choice in alias.choices:
                if isinstance(choice, str):
                    monkeypatch.delenv(choice, raising=False)
        elif isinstance(alias, str):
            monkeypatch.delenv(alias, raising=False)
    reset_settings()


def test_defaults_sin_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.app_mode == "demo"
    assert settings.dry_run is True
    assert settings.outreach_enabled is False
    assert settings.video_enabled is True
    assert settings.tz == "America/Santiago"
    assert settings.database_url == "sqlite:///./state/agencia.db"
    assert settings.llm_model == "grok-4.7"
    assert settings.llm_model_fast == "grok-4.6"
    assert settings.llm_base_url == "https://api.x.ai/v1"
    assert settings.hitl_value_clp == 2_800_000
    assert settings.hitl_response_rate == 0.12
    assert settings.hitl_min_sample == 30
    assert settings.mobile_autoreply_min_confidence == 0.8
    assert settings.scout_daily_limit == 30
    assert settings.diagnose_daily_limit == 15
    assert settings.email_outreach_daily_limit == 15
    assert settings.email_outreach_daily_max == 50
    assert settings.deposit_percent == 50
    assert settings.prices_include_iva is True
    assert settings.price_min_clp == 250_000
    assert settings.price_max_clp == 450_000
    assert settings.maintenance_price_clp is None
    assert settings.booking_provider == "calcom"
    assert settings.hosting_provider == "caddy"
    assert settings.agency_name == ""
    assert settings.secret_key == ""
    assert settings.resolved_secret_key
    assert len(settings.scout_category_list) == 15
    assert settings.cors_origin_list == [
        "http://localhost:8080",
        "http://localhost:4321",
    ]


def test_hitl_value_sale_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("HITL_VALUE_CLP", "123456")
    reset_settings()
    assert get_settings().hitl_value_clp == 123456
    assert needs_value_review(123456) is True
    assert needs_value_review(123455) is False


def test_reset_settings_relee_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("HITL_VALUE_CLP", "10")
    reset_settings()
    assert get_settings().hitl_value_clp == 10
    monkeypatch.setenv("HITL_VALUE_CLP", "20")
    assert get_settings().hitl_value_clp == 10
    reset_settings()
    assert get_settings().hitl_value_clp == 20


def test_alias_grok_y_calendly(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("GROK_API_KEY", "desde-grok")
    monkeypatch.setenv("CALENDLY_LINK", "https://cal.example/demo")
    reset_settings()
    settings = get_settings()
    assert settings.xai_api_key == "desde-grok"
    assert settings.booking_link == "https://cal.example/demo"


def test_xai_api_key_pisa_el_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("XAI_API_KEY", "desde-xai")
    monkeypatch.setenv("GROK_API_KEY", "desde-grok")
    reset_settings()
    assert get_settings().xai_api_key == "desde-xai"


def test_bools_y_mantencion_vacia(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "0")
    monkeypatch.setenv("OUTREACH_ENABLED", "1")
    monkeypatch.setenv("VIDEO_ENABLED", "false")
    monkeypatch.setenv("MAINTENANCE_PRICE_CLP", "")
    settings = Settings(_env_file=None)
    assert settings.dry_run is False
    assert settings.outreach_enabled is True
    assert settings.video_enabled is False
    assert settings.maintenance_price_clp is None
    monkeypatch.setenv("MAINTENANCE_PRICE_CLP", "15000")
    priced = Settings(_env_file=None)
    assert priced.maintenance_price_clp == 15_000


def test_env_de_raiz_pisa_engine_y_el_proceso_pisa_ambos(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_env(monkeypatch)
    engine_env = tmp_path / "engine.env"
    root_env = tmp_path / "root.env"
    engine_env.write_text(
        "APP_MODE=demo\nDRY_RUN=true\nHITL_VALUE_CLP=10\nAGENCY_NAME=engine\n",
        encoding="utf-8",
    )
    root_env.write_text(
        "APP_MODE=prod\nDRY_RUN=false\nAGENCY_NAME=raiz\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HITL_VALUE_CLP", "99")
    settings = Settings(_env_file=(engine_env, root_env))
    assert settings.app_mode == "prod"
    assert settings.dry_run is False
    assert settings.agency_name == "raiz"
    assert settings.hitl_value_clp == 99


def test_secreto_efimero_no_se_persiste_en_el_campo(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    first = Settings(_env_file=None)
    second = Settings(_env_file=None)
    assert first.secret_key == ""
    assert first.resolved_secret_key == second.resolved_secret_key
    assert len(first.resolved_secret_key) >= 16
