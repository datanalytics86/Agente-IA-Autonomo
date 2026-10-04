"""Configuración de entorno. Las variables de proceso pisan a los .env."""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("core.config")

ENGINE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = ENGINE_DIR.parent

SCOUT_CATEGORY_SLUGS: tuple[str, ...] = (
    "clinica-dental",
    "optica",
    "abogados",
    "estudio-contable",
    "peluqueria",
    "centro-estetica",
    "spa",
    "gimnasio",
    "cafeteria",
    "restaurante",
    "taller-mecanico",
    "inmobiliaria",
    "veterinaria",
    "escuela-idiomas",
    "ferreteria",
)

_DEFAULT_COMMUNES = (
    "Providencia,Las Condes,Ñuñoa,Maipú,Viña del Mar,Valparaíso,Concepción,Temuco,La Serena"
)
_DEFAULT_CATEGORIES = ",".join(SCOUT_CATEGORY_SLUGS)

# Valor de proceso: no se escribe a disco. Cambia al reiniciar.
_EPHEMERAL_SECRET = secrets.token_urlsafe(32)
_ephemeral_warned = False


def _env_files() -> tuple[Path, ...]:
    """engine/.env primero; el .env de la raíz lo pisa. Los que no existen se omiten."""
    candidates = (ENGINE_DIR / ".env", REPO_ROOT / ".env")
    return tuple(path for path in candidates if path.is_file())


def _warn_ephemeral_once() -> None:
    global _ephemeral_warned
    if _ephemeral_warned:
        return
    logger.warning(
        "SECRET_KEY vacío en demo: se usa un valor efímero de este proceso, no persistido"
    )
    _ephemeral_warned = True


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


class Settings(BaseSettings):
    """Todas las variables del contrato de entorno. Sin credenciales el proceso arranca."""

    model_config = SettingsConfigDict(
        env_file=_env_files() or None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_mode: Literal["demo", "prod"] = "demo"
    dry_run: bool = True
    outreach_enabled: bool = False
    tz: str = "America/Santiago"
    video_enabled: bool = True

    database_url: str = "sqlite:///./state/agencia.db"
    secret_key: str = ""
    admin_email: str = ""
    admin_password_hash: str = ""
    public_base_url: str = "http://localhost"
    admin_base_url: str = "http://localhost:8080"
    cors_origins: str = "http://localhost:8080,http://localhost:4321"

    agency_name: str = ""
    agency_legal_name: str = ""
    agency_rut: str = ""
    agency_email: str = ""
    agency_address: str = ""

    xai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("XAI_API_KEY", "GROK_API_KEY"),
    )
    llm_base_url: str = "https://api.x.ai/v1"
    llm_model: str = "grok-4.7"
    llm_model_fast: str = "grok-4.6"
    llm_daily_budget_usd: float = 3

    google_places_api_key: str = ""
    pagespeed_api_key: str = ""
    scout_communes: str = _DEFAULT_COMMUNES
    scout_categories: str = _DEFAULT_CATEGORIES
    scout_daily_limit: int = 30
    scout_min_rating: float = 4.0
    scout_min_reviews: int = 15
    diagnose_daily_limit: int = 15

    resend_api_key: str = ""
    email_tx_from: str = ""
    outreach_smtp_host: str = ""
    outreach_smtp_port: int = 587
    outreach_smtp_user: str = ""
    outreach_smtp_password: str = ""
    outreach_imap_host: str = ""
    outreach_imap_port: int = 993
    outreach_imap_user: str = ""
    outreach_imap_password: str = ""
    outreach_from: str = ""
    email_outreach_daily_limit: int = 15
    email_outreach_daily_max: int = 50
    followup_1_business_days: int = 4
    followup_2_business_days: int = 9

    booking_provider: Literal["calcom", "calendly"] = "calcom"
    booking_link: str = Field(
        default="",
        validation_alias=AliasChoices("BOOKING_LINK", "CALENDLY_LINK"),
    )
    calcom_webhook_secret: str = ""
    calendly_webhook_signing_key: str = ""

    mp_access_token: str = ""
    mp_webhook_secret: str = ""
    prices_include_iva: bool = True
    deposit_percent: int = 50
    price_min_clp: int = 250_000
    price_max_clp: int = 450_000
    maintenance_price_clp: int | None = None

    meta_app_secret: str = ""
    meta_verify_token: str = ""
    ig_access_token: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""

    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    sentry_dsn: str = ""

    hosting_provider: Literal["caddy", "cloudflare_pages"] = "caddy"
    client_sites_dir: str = "engine/output/clients"
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""

    notify_email: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    hitl_value_clp: int = 2_800_000
    hitl_response_rate: float = 0.12
    hitl_min_sample: int = 30
    mobile_autoreply_min_confidence: float = 0.8
    demo_ttl_days: int = 30
    retention_days: int = 120
    job_max_retries: int = 3

    @field_validator("maintenance_price_clp", mode="before")
    @classmethod
    def _blank_maintenance(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def _note_empty_secret(self) -> Self:
        if self.app_mode == "demo" and self.secret_key == "":
            _warn_ephemeral_once()
        return self

    @property
    def resolved_secret_key(self) -> str:
        if self.secret_key:
            return self.secret_key
        if self.app_mode == "demo":
            return _EPHEMERAL_SECRET
        return ""

    @property
    def cors_origin_list(self) -> list[str]:
        return _csv(self.cors_origins)

    @property
    def scout_commune_list(self) -> list[str]:
        return _csv(self.scout_communes)

    @property
    def scout_category_list(self) -> list[str]:
        return _csv(self.scout_categories)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    """Limpia la caché. Los tests lo llaman después de cambiar el entorno."""
    get_settings.cache_clear()
