"""Reglas HITL. Los umbrales salen del entorno y, por canal, de settings_kv."""

from __future__ import annotations

from sqlalchemy.orm import Session

from core.config import get_settings
from db.repositories import SettingsRepository


def needs_value_review(estimated_value_clp: int) -> bool:
    """True si el deal debe ir a revision antes de un envío o una propuesta."""
    return estimated_value_clp >= get_settings().hitl_value_clp


def response_rate(sent: int, responded: int) -> float:
    if sent < 0 or responded < 0:
        raise ValueError("los conteos no pueden ser negativos")
    if sent == 0:
        return 0.0
    return responded / sent


def channel_should_pause(
    channel: str,
    sent: int,
    responded: int,
    *,
    session: Session | None = None,
) -> bool:
    """Pausa el canal si la muestra alcanza el mínimo y la tasa queda bajo el umbral."""
    settings = get_settings()
    if sent <= 0 or sent < settings.hitl_min_sample:
        return False
    return response_rate(sent, responded) < _response_threshold(channel, session)


def _response_threshold(channel: str, session: Session | None) -> float:
    default = get_settings().hitl_response_rate
    if session is None or not channel.strip():
        return default
    raw = SettingsRepository(session).get("hitl_response_rate_by_channel")
    if not isinstance(raw, dict) or channel not in raw:
        return default
    try:
        return float(raw[channel])
    except (TypeError, ValueError):
        return default
