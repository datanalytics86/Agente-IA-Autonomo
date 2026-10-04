"""Mercado Pago. El webhook solo identifica el pago; el estado sale de fetch_payment."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict

from core.config import Settings
from integrations.errors import ProviderRequestError, WebhookSignatureError
from integrations.headers import header

MP_API = "https://api.mercadopago.com"


class Preference(BaseModel):
    preference_id: str
    checkout_url: str
    order_id: str
    amount_clp: int


class PaymentFact(BaseModel):
    """Hecho leído del proveedor. Dos lecturas del mismo id devuelven el mismo hecho."""

    model_config = ConfigDict(frozen=True)

    provider: str = "mercadopago"
    provider_payment_id: str
    status: str
    amount_clp: int
    order_id: str | None = None
    approved: bool = False


class PaymentProvider(Protocol):
    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference: ...

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> str: ...

    def fetch_payment(self, provider_payment_id: str) -> PaymentFact: ...


def _eq(expected: str, presented: str) -> bool:
    left = expected.encode()
    right = presented.strip().encode()
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _signed_data_id(data_id: str) -> str:
    """MP pide minúsculas solo cuando el id trae letras."""
    cleaned = data_id.strip()
    if any(character.isalpha() for character in cleaned):
        return cleaned.lower()
    return cleaned


def mp_manifest(*, data_id: str, request_id: str, ts: str) -> str:
    parts: list[str] = []
    signed_id = _signed_data_id(data_id)
    if signed_id:
        parts.append(f"id:{signed_id}")
    if request_id:
        parts.append(f"request-id:{request_id}")
    parts.append(f"ts:{ts}")
    return ";".join(parts) + ";"


def verify_mp_signature(
    *,
    secret: str,
    x_signature: str,
    x_request_id: str,
    data_id: str,
) -> None:
    """Falla si `x-signature` no calza con el manifiesto `id;request-id;ts;`."""
    if not secret:
        raise WebhookSignatureError("secreto de mercado pago vacío")
    if not x_signature or not data_id.strip():
        raise WebhookSignatureError("firma de mercado pago ausente")
    parts: dict[str, str] = {}
    for piece in x_signature.split(","):
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        parts[key.strip()] = value.strip()
    ts = parts.get("ts", "")
    presented = parts.get("v1", "")
    if not ts or not presented:
        raise WebhookSignatureError("firma de mercado pago incompleta")
    expected = hmac.new(
        secret.encode(),
        mp_manifest(data_id=data_id, request_id=x_request_id, ts=ts).encode(),
        hashlib.sha256,
    ).hexdigest()
    if not _eq(expected, presented):
        raise WebhookSignatureError("firma de mercado pago inválida")


def _clp(value: object) -> int:
    try:
        amount = Decimal(str(value))
    except Exception as exc:
        raise ProviderRequestError("monto CLP ilegible") from exc
    if amount != amount.to_integral_value():
        raise ProviderRequestError("el monto CLP no es entero")
    return int(amount)


def _payment_id(value: object) -> str:
    cleaned = str(value).strip()
    if not cleaned or any(char in cleaned for char in "/\\?#"):
        raise ValueError("id de pago inválido")
    return cleaned


def _loads(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("webhook de pago no es JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("webhook de pago no es un objeto")
    return payload


def _mode_block(settings: Settings) -> str | None:
    if settings.dry_run:
        return "dry_run"
    if settings.app_mode != "prod":
        return "app_mode"
    if not settings.mp_access_token.strip():
        return "credential"
    return None


class MercadoPagoProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _guard(self) -> None:
        reason = _mode_block(self.settings)
        if reason:
            raise ProviderRequestError(reason)

    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference:
        self._guard()
        if amount_clp <= 0:
            raise ValueError("monto CLP inválido")
        payload: dict[str, object] = {
            "items": [
                {
                    "title": title,
                    "quantity": 1,
                    "currency_id": "CLP",
                    "unit_price": amount_clp,
                }
            ],
            "external_reference": order_id,
        }
        base = self.settings.public_base_url.rstrip("/")
        if base:
            payload["notification_url"] = f"{base}/webhooks/mercadopago"
            payload["back_urls"] = {
                "success": f"{base}/pago/exito",
                "pending": f"{base}/pago/pendiente",
                "failure": f"{base}/pago/error",
            }
            payload["auto_return"] = "approved"
        response = httpx.post(
            f"{MP_API}/checkout/preferences",
            headers={
                "Authorization": f"Bearer {self.settings.mp_access_token}",
                "X-Idempotency-Key": order_id,
            },
            json=payload,
            timeout=20.0,
            trust_env=False,
        )
        if response.status_code not in {200, 201}:
            raise ProviderRequestError(f"mercadopago_{response.status_code}")
        body = response.json()
        preference_id = str(body.get("id") or "")
        checkout = str(body.get("init_point") or body.get("sandbox_init_point") or "")
        if not preference_id or not checkout:
            raise ProviderRequestError("preferencia incompleta")
        return Preference(
            preference_id=preference_id,
            checkout_url=checkout,
            order_id=order_id,
            amount_clp=amount_clp,
        )

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> str:
        """Devuelve el id del pago. No mira `status` y no marca nada como pagado."""
        payload = _loads(body)
        data = payload.get("data")
        raw_id = data.get("id") if isinstance(data, dict) else None
        if raw_id is None:
            raw_id = payload.get("id") if payload.get("type") == "payment" else None
        if raw_id is None:
            raise ValueError("webhook sin id de pago")
        payment_id = _payment_id(raw_id)
        verify_mp_signature(
            secret=self.settings.mp_webhook_secret,
            x_signature=header(headers, "x-signature"),
            x_request_id=header(headers, "x-request-id"),
            data_id=payment_id,
        )
        return payment_id

    def fetch_payment(self, provider_payment_id: str) -> PaymentFact:
        """Lee el pago en MP. No lo persiste: el mismo id vuelve a dar el mismo hecho."""
        self._guard()
        payment_id = _payment_id(provider_payment_id)
        response = httpx.get(
            f"{MP_API}/v1/payments/{quote(payment_id, safe='')}",
            headers={"Authorization": f"Bearer {self.settings.mp_access_token}"},
            timeout=20.0,
            trust_env=False,
        )
        if response.status_code != 200:
            raise ProviderRequestError(f"mercadopago_{response.status_code}")
        body = response.json()
        returned = _payment_id(body.get("id"))
        if returned != payment_id:
            raise ProviderRequestError("el id devuelto no coincide")
        status = str(body.get("status") or "")
        if not status:
            raise ProviderRequestError("pago sin estado")
        order_id = body.get("external_reference")
        return PaymentFact(
            provider_payment_id=returned,
            status=status,
            amount_clp=_clp(body.get("transaction_amount")),
            order_id=str(order_id) if order_id else None,
            approved=status == "approved",
        )


class FakePaymentProvider:
    def __init__(self) -> None:
        self.preferences: dict[str, Preference] = {}
        self.payments: dict[str, PaymentFact] = {}
        self._seq = 0

    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference:
        del title
        if amount_clp <= 0:
            raise ValueError("monto CLP inválido")
        self._seq += 1
        preference = Preference(
            preference_id=f"fake-pref-{self._seq}",
            checkout_url=f"https://pay.invalid/checkout/{self._seq}",
            order_id=order_id,
            amount_clp=amount_clp,
        )
        self.preferences[order_id] = preference
        return preference

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> str:
        """Ignora un `status: approved` del cuerpo. Solo devuelve el id."""
        del headers
        payload = _loads(body)
        data = payload.get("data")
        raw_id = data.get("id") if isinstance(data, dict) else payload.get("id")
        if raw_id is None:
            raise ValueError("webhook sin id de pago")
        return _payment_id(raw_id)

    def fetch_payment(self, provider_payment_id: str) -> PaymentFact:
        payment_id = _payment_id(provider_payment_id)
        staged = self.payments.get(payment_id)
        if staged is not None:
            return staged
        return PaymentFact(
            provider_payment_id=payment_id,
            status="pending",
            amount_clp=0,
            order_id=None,
            approved=False,
        )

    def stage(self, fact: PaymentFact) -> None:
        self.payments[fact.provider_payment_id] = fact


def build_payments(settings: Settings) -> PaymentProvider:
    if settings.app_mode == "demo" or settings.dry_run or not settings.mp_access_token.strip():
        return FakePaymentProvider()
    return MercadoPagoProvider(settings)
