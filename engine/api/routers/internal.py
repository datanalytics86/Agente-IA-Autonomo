"""Endpoint ask de Caddy. No se publica: red interna o token, con rate limit."""

from __future__ import annotations

import hmac
import ipaddress
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.deps import Db
from api.errors import error_body
from api.services import domain_authorized
from core.config import get_settings

router = APIRouter(tags=["internal"])

_WINDOW_SECONDS = 60.0
_checks: dict[str, list[float]] = {}


def reset_domain_checks() -> None:
    _checks.clear()


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _loopback(host: str) -> bool:
    if host in {"testclient", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _in_internal_net(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    for item in _csv(get_settings().internal_check_nets):
        try:
            if "/" in item:
                if address in ipaddress.ip_network(item, strict=False):
                    return True
            elif address == ipaddress.ip_address(item):
                return True
        except ValueError:
            continue
    return False


def client_may_check(host: str, header: str) -> bool:
    """Loopback, red configurada o token. Una IP privada no basta por sí sola.

    El host es el par TCP. X-Forwarded-For no autoriza.
    """
    expected = get_settings().internal_check_token.strip()
    same = bool(expected and header and len(header) == len(expected))
    if same and hmac.compare_digest(header, expected):
        return True
    if _loopback(host):
        return True
    return _in_internal_net(host)


def domain_check_blocked(host: str) -> bool:
    limit = get_settings().internal_check_per_minute
    if limit < 1:
        limit = 1
    now = time.monotonic()
    recent = [item for item in _checks.get(host, []) if now - item < _WINDOW_SECONDS]
    if len(recent) >= limit:
        _checks[host] = recent
        return True
    recent.append(now)
    _checks[host] = recent
    return False


@router.get("/api/internal/domain-check", response_model=None)
def domain_check(domain: str, request: Request, session: Db) -> JSONResponse | dict[str, bool]:
    host = request.client.host if request.client else ""
    if domain_check_blocked(host or "unknown"):
        return JSONResponse(
            status_code=429,
            content=error_body("rate_limited", "demasiadas consultas; espera un minuto"),
        )
    header = request.headers.get("x-internal-token", "")
    if not client_may_check(host, header) or not domain_authorized(session, domain):
        return JSONResponse(
            status_code=404,
            content=error_body("not_found", "dominio no autorizado"),
        )
    return {"allowed": True}
