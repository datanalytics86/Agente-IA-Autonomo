"""La configuración sale del entorno, con alias y archivos .env en el orden del contrato."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import AliasChoices

from api.app import should_create_schema
from api.security import dump_session, make_baja_token
from core.config import ProdConfigError, Settings, get_settings, reset_settings
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
        "APP_MODE=prod\nDRY_RUN=false\nAGENCY_NAME=raiz\n"
        "SECRET_KEY=raiz-secret-key-de-produccion-32\n"
        "DATABASE_URL=sqlite:///./state/override.db\n"
        "ADMIN_EMAIL=admin@raiz.example\n"
        "ADMIN_PASSWORD_HASH=hash-raiz\n"
        "PUBLIC_BASE_URL=https://raiz.example\n"
        "AGENCY_EMAIL=hola@raiz.example\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HITL_VALUE_CLP", "99")
    settings = Settings(_env_file=(engine_env, root_env))
    assert settings.app_mode == "prod"
    assert settings.dry_run is False
    assert settings.agency_name == "raiz"
    assert settings.hitl_value_clp == 99


_PROD: dict[str, str] = {
    "app_mode": "prod",
    "secret_key": "s" * 32,
    "database_url": "sqlite:///:memory:",
    "admin_email": "admin@example.com",
    "admin_password_hash": "hash-de-prueba",
    "public_base_url": "https://agencia.example",
    "agency_name": "Agencia Norte",
    "agency_email": "hola@agencia.example",
}

_PROD_ENV = {
    "SECRET_KEY": "SECRET_KEY",
    "DATABASE_URL": "DATABASE_URL",
    "ADMIN_EMAIL": "ADMIN_EMAIL",
    "ADMIN_PASSWORD_HASH": "ADMIN_PASSWORD_HASH",
    "PUBLIC_BASE_URL": "PUBLIC_BASE_URL",
    "AGENCY_NAME": "AGENCY_NAME",
    "AGENCY_EMAIL": "AGENCY_EMAIL",
}


def _prod_settings(**overrides: str) -> Settings:
    data = dict(_PROD)
    data.update(overrides)
    return Settings(_env_file=None, **data)


def test_secreto_efimero_no_se_persiste_en_el_campo(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    first = Settings(_env_file=None)
    second = Settings(_env_file=None)
    assert first.secret_key == ""
    assert first.resolved_secret_key == second.resolved_secret_key
    assert len(first.resolved_secret_key) >= 16


def test_prod_completo_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    settings = _prod_settings()
    assert settings.app_mode == "prod"
    assert settings.resolved_secret_key == "s" * 32


def test_prod_sin_secret_key_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    for key, value in _PROD.items():
        if key == "secret_key":
            monkeypatch.setenv("SECRET_KEY", "")
        else:
            monkeypatch.setenv(key.upper(), value)
    reset_settings()
    with pytest.raises(ProdConfigError, match="falta SECRET_KEY") as caught:
        get_settings()
    assert "ADMIN_EMAIL" not in str(caught.value)
    assert "AGENCY_NAME" not in str(caught.value)


@pytest.mark.parametrize(
    ("field", "env_name", "fragment"),
    [
        ("secret_key", "SECRET_KEY", "falta SECRET_KEY"),
        ("database_url", "DATABASE_URL", "falta DATABASE_URL"),
        ("admin_email", "ADMIN_EMAIL", "falta ADMIN_EMAIL"),
        ("admin_password_hash", "ADMIN_PASSWORD_HASH", "falta ADMIN_PASSWORD_HASH"),
        ("public_base_url", "PUBLIC_BASE_URL", "falta PUBLIC_BASE_URL"),
        ("agency_name", "AGENCY_NAME", "falta AGENCY_NAME"),
        ("agency_email", "AGENCY_EMAIL", "falta AGENCY_EMAIL"),
    ],
)
def test_prod_sin_variable_obligatoria_no_arranca(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    env_name: str,
    fragment: str,
) -> None:
    _clear_env(monkeypatch)
    data = {key: value for key, value in _PROD.items() if key != field}
    with pytest.raises(ProdConfigError, match=fragment) as caught:
        Settings(_env_file=None, **data)
    message = str(caught.value)
    assert env_name in message
    for other in _PROD_ENV:
        if other != env_name:
            assert other not in message
    monkeypatch.setenv("APP_MODE", "prod")
    for key, value in _PROD.items():
        monkeypatch.setenv(key.upper(), "" if key == field else value)
    reset_settings()
    with pytest.raises(ProdConfigError, match=fragment):
        get_settings()


def test_prod_secret_key_corta_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    with pytest.raises(ProdConfigError, match="SECRET_KEY debe tener al menos 32 caracteres"):
        _prod_settings(secret_key="x" * 31)


def test_prod_public_base_url_sin_https_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    with pytest.raises(ProdConfigError, match="PUBLIC_BASE_URL debe empezar por https"):
        _prod_settings(public_base_url="http://localhost")


def test_prod_no_firma_sesiones_ni_baja_con_clave_vacia(monkeypatch: pytest.MonkeyPatch) -> None:
    broken = Settings.model_construct(app_mode="prod", secret_key="", public_base_url="https://x")
    monkeypatch.setattr("api.security.get_settings", lambda: broken)
    with pytest.raises(ProdConfigError, match="SECRET_KEY"):
        dump_session("user-1", "admin@example.com")
    with pytest.raises(ProdConfigError, match="SECRET_KEY"):
        make_baja_token("lead-1")


def test_create_all_solo_en_sqlite_de_demo() -> None:
    demo_sqlite = Settings.model_construct(
        app_mode="demo",
        database_url="sqlite:///./state/agencia.db",
    )
    demo_memory = Settings.model_construct(app_mode="demo", database_url="sqlite:///:memory:")
    demo_postgres = Settings.model_construct(
        app_mode="demo",
        database_url="postgresql+psycopg://localhost/agencia",
    )
    prod_sqlite = Settings.model_construct(
        app_mode="prod",
        database_url="sqlite:///./state/agencia.db",
    )
    assert should_create_schema(demo_sqlite) is True
    assert should_create_schema(demo_memory) is True
    assert should_create_schema(demo_postgres) is False
    assert should_create_schema(prod_sqlite) is False
