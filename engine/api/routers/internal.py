"""Endpoint ask de Caddy. Solo responde 200 desde la red interna."""

from __future__ import annotations

import hmac
import ipaddress

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.deps import Db
from api.errors import error_body
from api.services import domain_authorized
from core.config import get_settings

router = APIRouter(tags=["internal"])


def _loopback(host: str) -> bool:
    if host in {"testclient", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def client_may_check(host: str, header: str) -> bool:
    """Loopback, o un header que coincide con INTERNAL_CHECK_TOKEN. Una IP privada no basta."""
    expected = get_settings().internal_check_token.strip()
    same = bool(expected and header and len(header) == len(expected))
    if same and hmac.compare_digest(header, expected):
        return True
    return _loopback(host)


@router.get("/api/internal/domain-check", response_model=None)
def domain_check(domain: str, request: Request, session: Db) -> JSONResponse | dict[str, bool]:
    host = request.client.host if request.client else ""
    header = request.headers.get("x-internal-token", "")
    if not client_may_check(host, header) or not domain_authorized(session, domain):
        return JSONResponse(
            status_code=404,
            content=error_body("not_found", "dominio no autorizado"),
        )
    return {"allowed": True}
