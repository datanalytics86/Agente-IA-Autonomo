"""Endpoint ask de Caddy. Solo responde 200 desde la red interna."""

from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.deps import Db
from api.errors import error_body
from api.services import domain_authorized

router = APIRouter(tags=["internal"])


def _internal(host: str) -> bool:
    if host in {"testclient", "localhost"}:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


@router.get("/api/internal/domain-check", response_model=None)
def domain_check(domain: str, request: Request, session: Db) -> JSONResponse | dict[str, bool]:
    host = request.client.host if request.client else ""
    if not _internal(host) or not domain_authorized(session, domain):
        return JSONResponse(
            status_code=404,
            content=error_body("not_found", "dominio no autorizado"),
        )
    return {"allowed": True}
