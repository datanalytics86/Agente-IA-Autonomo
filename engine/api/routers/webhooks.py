"""Webhooks con firma. Mercado Pago no confía en el body: consulta fetch_payment."""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from api.deps import Db, Payments
from api.errors import ApiError
from api.security import (
    verify_calcom,
    verify_calendly,
    verify_mercadopago,
    verify_meta,
    verify_svix,
)
from api.services import accept_signed_event, apply_payment, resend_secret, webhook_event_id
from core.config import get_settings

router = APIRouter(tags=["webhooks"])


async def _raw_body(request: Request) -> bytes:
    return await request.body()


RawBody = Annotated[bytes, Depends(_raw_body)]


def _headers(request: Request) -> dict[str, str]:
    mapped = {key.lower(): value for key, value in request.headers.items()}
    query_id = request.query_params.get("data.id")
    if query_id:
        mapped["x-data-id"] = query_id
    return mapped


def _require(ok: bool) -> None:
    if not ok:
        raise ApiError(401, "invalid_signature", "firma inválida")


@router.post("/webhooks/mercadopago")
def mercadopago(body: RawBody, request: Request, session: Db, payments: Payments) -> dict[str, Any]:
    headers = _headers(request)
    signed_id = verify_mercadopago(
        get_settings().mp_webhook_secret,
        body,
        headers,
        request.query_params.get("data.id"),
    )
    try:
        parsed_id = payments.parse_webhook(body, headers)
    except ValueError as exc:
        raise ApiError(401, "invalid_signature", "firma inválida") from exc
    if parsed_id != signed_id:
        raise ApiError(401, "invalid_signature", "firma inválida")
    try:
        fact = payments.fetch_payment(parsed_id)
    except KeyError:
        return {"ok": True, "ignored": True}
    return apply_payment(session, fact)


@router.post("/webhooks/calcom")
def calcom(body: RawBody, request: Request, session: Db) -> dict[str, Any]:
    headers = _headers(request)
    _require(
        verify_calcom(
            get_settings().calcom_webhook_secret,
            body,
            headers.get("x-cal-signature-256", ""),
        )
    )
    return accept_signed_event(session, "calcom", webhook_event_id(headers, body), body)


@router.post("/webhooks/calendly")
def calendly(body: RawBody, request: Request, session: Db) -> dict[str, Any]:
    headers = _headers(request)
    _require(
        verify_calendly(
            get_settings().calendly_webhook_signing_key,
            body,
            headers.get("calendly-webhook-signature", ""),
        )
    )
    return accept_signed_event(session, "calendly", webhook_event_id(headers, body), body)


@router.post("/webhooks/email")
def email_hook(body: RawBody, request: Request, session: Db) -> dict[str, Any]:
    headers = _headers(request)
    _require(verify_svix(resend_secret(), body, headers))
    event_id = webhook_event_id(headers, body)
    return accept_signed_event(session, "email", event_id, body)


@router.get("/webhooks/meta")
def meta_verify(request: Request) -> PlainTextResponse:
    settings = get_settings()
    mode = request.query_params.get("hub.mode", "")
    token = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    expected = settings.meta_verify_token
    if mode == "subscribe" and expected and challenge and len(token) == len(expected):
        if hmac.compare_digest(token, expected):
            return PlainTextResponse(challenge)
    raise ApiError(401, "invalid_signature", "verificación rechazada")


@router.post("/webhooks/meta")
def meta_hook(body: RawBody, request: Request, session: Db) -> dict[str, Any]:
    headers = _headers(request)
    signature = headers.get("x-hub-signature-256", "")
    _require(verify_meta(get_settings().meta_app_secret, body, signature))
    return accept_signed_event(session, "meta", webhook_event_id(headers, body), body)
