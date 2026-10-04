"""Formularios públicos, baja, demo y portal del cliente."""

from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from api.deps import Db, Payments, client_ip
from api.errors import ApiError
from api.schemas import (
    Accepted,
    BajaIn,
    CheckoutIn,
    CheckoutOut,
    ContactoIn,
    DerechosIn,
    DiagnosticoIn,
    FeedbackIn,
    Package,
    ProjectPublic,
)
from api.security import read_baja_token, turnstile_accepts
from api.services import (
    _packages_view,
    apply_baja,
    approve_project_public,
    checkout,
    load_demo,
    preview_html,
    project_public,
    save_feedback,
    save_intake,
    submit_contacto,
    submit_diagnostico,
    submit_rights,
)
from db.models import new_id

router = APIRouter(tags=["public"])
_ROBOTS = {"X-Robots-Tag": "noindex, nofollow"}
_BAJA_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex, nofollow">
<title>Baja</title>
</head>
<body>
<p>Confirma la baja de comunicaciones comerciales.</p>
</body>
</html>
"""


def _gate(honeypot: str, token: str, request: Request) -> Accepted | None:
    if honeypot.strip():
        return Accepted(id=new_id(), status="accepted")
    if not turnstile_accepts(token, client_ip(request)):
        raise ApiError(403, "turnstile_rejected", "no se pudo verificar el envío")
    return None


@router.get("/api/public/paquetes", response_model=list[Package])
def paquetes(session: Db) -> list[dict[str, Any]]:
    return _packages_view(session)


@router.post("/api/public/diagnostico", response_model=Accepted, status_code=202)
def diagnostico(payload: DiagnosticoIn, request: Request, session: Db) -> Accepted:
    gated = _gate(payload.honeypot, payload.turnstile_token, request)
    if gated is not None:
        return gated
    if payload.consent is not True:
        raise ApiError(422, "consent_required", "se requiere consentimiento explícito")
    created = submit_diagnostico(
        session,
        business=payload.business,
        email=payload.email,
        commune=payload.commune,
        category=payload.category,
        consent_text=payload.consent_text,
        website_url=payload.website_url,
        ip=client_ip(request),
    )
    return Accepted(id=created["id"], status=created["status"])


@router.post("/api/public/contacto", response_model=Accepted, status_code=202)
def contacto(payload: ContactoIn, request: Request, session: Db) -> Accepted:
    gated = _gate(payload.honeypot, payload.turnstile_token, request)
    if gated is not None:
        return gated
    if payload.consent is not True:
        raise ApiError(422, "consent_required", "se requiere consentimiento explícito")
    created = submit_contacto(
        session,
        name=payload.name,
        email=payload.email,
        message=payload.message,
        ip=client_ip(request),
    )
    return Accepted(id=created["id"], status=created["status"])


@router.post("/api/public/checkout", response_model=CheckoutOut, status_code=201)
def checkout_route(payload: CheckoutIn, session: Db, payments: Payments) -> CheckoutOut:
    created = checkout(
        session,
        payments,
        package_code=payload.package_code,
        lead_id=payload.lead_id,
    )
    return CheckoutOut(order_id=created["order_id"], checkout_url=created["checkout_url"])


@router.get("/api/public/baja")
def baja_get(token: str) -> HTMLResponse:
    read_baja_token(token)
    return HTMLResponse(_BAJA_HTML, headers=_ROBOTS)


@router.post("/api/public/baja")
def baja_post(payload: BajaIn, session: Db) -> dict[str, bool]:
    return apply_baja(session, payload.token)


@router.post("/u/{token}")
def one_click(token: str, session: Db) -> dict[str, bool]:
    return apply_baja(session, token)


@router.post("/api/public/derechos", response_model=Accepted, status_code=202)
def derechos(payload: DerechosIn, request: Request, session: Db) -> Accepted:
    gated = _gate(payload.honeypot, payload.turnstile_token, request)
    if gated is not None:
        return gated
    created = submit_rights(
        session,
        kind=payload.kind,
        email=payload.email,
        details=payload.details,
    )
    return Accepted(id=created["id"], status=created["status"])


@router.get("/demo/{token}", response_model=None)
def demo(token: str, session: Db) -> HTMLResponse | JSONResponse:
    status_code, body, is_html = load_demo(session, token)
    if is_html and isinstance(body, str):
        return HTMLResponse(body, status_code=status_code, headers=_ROBOTS)
    return JSONResponse(body, status_code=status_code, headers=_ROBOTS)


@router.get("/api/public/proyecto/{token}", response_model=ProjectPublic)
def proyecto(token: str, session: Db) -> dict[str, Any]:
    return project_public(session, token)


@router.get("/pago/fake/{pref_id}", response_model=None)
def pago_fake(pref_id: str) -> HTMLResponse:
    safe = html.escape(pref_id)
    page = (
        '<!doctype html><html lang="es-CL"><head>'
        '<meta charset="utf-8">'
        '<meta name="robots" content="noindex, nofollow">'
        "<title>Pago simulado</title></head><body>"
        "<p>Pago simulado. No se hizo ningún cobro.</p>"
        f"<p>Referencia {safe}.</p>"
        "</body></html>"
    )
    return HTMLResponse(page, headers=_ROBOTS)


@router.get("/api/public/proyecto/{token}/preview", response_model=None)
def proyecto_preview(token: str, session: Db) -> HTMLResponse:
    return HTMLResponse(preview_html(session, token), headers=_ROBOTS)


@router.post("/api/public/proyecto/{token}/intake")
def intake(token: str, payload: dict[str, Any], session: Db) -> dict[str, bool]:
    return save_intake(session, token, payload)


@router.post("/api/public/proyecto/{token}/feedback", status_code=202)
def feedback(token: str, payload: FeedbackIn, session: Db) -> dict[str, str]:
    return save_feedback(session, token, payload.text)


@router.post("/api/public/proyecto/{token}/aprobar")
def aprobar(token: str, session: Db) -> dict[str, str]:
    return approve_project_public(session, token)
