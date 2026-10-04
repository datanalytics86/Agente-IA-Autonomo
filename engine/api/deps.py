"""Dependencias de request y el protocolo de pagos.

El adaptador real de Mercado Pago es de A5 (`integrations.payments`).
Si no está, o no hay token, o el proceso está en demo/dry-run, se usa
el fake local. No abre red ni cobra.
"""

from __future__ import annotations

import hmac
import importlib
import secrets
from collections.abc import Iterator, Mapping
from typing import Annotated, Protocol

from fastapi import Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import Response

from api.errors import ApiError
from api.security import (
    CSRF_COOKIE,
    CSRF_HEADER,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    burn_password_check,
    clear_login_failures,
    cookies_secure,
    dump_session,
    load_session,
    login_blocked,
    mp_payment_id,
    record_login_failure,
    verify_password,
)
from core.config import Settings, get_settings
from db.models import User, new_id
from db.session import session_scope


class Preference(BaseModel):
    id: str
    checkout_url: str


class PaymentFact(BaseModel):
    provider_payment_id: str
    status: str
    amount_clp: int
    order_id: str | None = None
    lead_id: str | None = None
    package_code: str | None = None
    raw: dict[str, object] = Field(default_factory=dict)


class PaymentProvider(Protocol):
    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference: ...

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> str: ...

    def fetch_payment(self, provider_payment_id: str) -> PaymentFact: ...


class LocalPaymentProvider:
    """Fake idempotente. `remember` deja un pago para que el webhook lo consulte."""

    def __init__(self, public_base_url: str) -> None:
        base = public_base_url.rstrip("/") or "http://localhost"
        self.public_base_url = base
        self._payments: dict[str, PaymentFact] = {}
        self._preferences: dict[str, tuple[str, int]] = {}

    def remember(self, fact: PaymentFact) -> None:
        self._payments[fact.provider_payment_id] = fact

    def create_preference(self, order_id: str, title: str, amount_clp: int) -> Preference:
        pref_id = new_id()
        self._preferences[pref_id] = (order_id, amount_clp)
        url = (
            f"{self.public_base_url}/pago/fake/{pref_id}"
            f"?order={order_id}&amount={amount_clp}&title={title[:40]}"
        )
        return Preference(id=pref_id, checkout_url=url)

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> str:
        return mp_payment_id(body, headers.get("x-data-id"))

    def fetch_payment(self, provider_payment_id: str) -> PaymentFact:
        fact = self._payments.get(provider_payment_id)
        if fact is not None:
            return fact
        staged = self._preferences.get(provider_payment_id)
        if staged is None:
            raise KeyError(provider_payment_id)
        order_id, amount_clp = staged
        return PaymentFact(
            provider_payment_id=provider_payment_id,
            status="approved",
            amount_clp=amount_clp,
            order_id=order_id,
        )


def build_payment_provider(settings: Settings) -> PaymentProvider:
    needs_fake = (
        settings.app_mode == "demo" or settings.dry_run or not settings.mp_access_token.strip()
    )
    if not needs_fake:
        try:
            module = importlib.import_module("integrations.payments")
            factory = getattr(module, "build_payment_provider", None)
        except ImportError:
            factory = None
        if factory is not None:
            built = factory(settings)
            if built is not None:
                return built
    return LocalPaymentProvider(settings.public_base_url)


def get_db() -> Iterator[Session]:
    with session_scope() as session:
        yield session


Db = Annotated[Session, Depends(get_db)]


def get_payment_provider(request: Request) -> PaymentProvider:
    provider = getattr(request.app.state, "payment_provider", None)
    if provider is None:
        provider = build_payment_provider(get_settings())
        request.app.state.payment_provider = provider
    return provider


Payments = Annotated[PaymentProvider, Depends(get_payment_provider)]


def client_ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def require_user(request: Request, session: Db) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "unauthenticated", "sesión requerida")
    data = load_session(token)
    user = session.get(User, data["uid"])
    if user is None:
        raise ApiError(401, "unauthenticated", "sesión inválida")
    return user


AuthUser = Annotated[User, Depends(require_user)]


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    if not cookie or not header or len(cookie) != len(header):
        raise ApiError(403, "csrf_invalid", "falta o no coincide el token CSRF")
    if not hmac.compare_digest(cookie, header):
        raise ApiError(403, "csrf_invalid", "falta o no coincide el token CSRF")


def apply_auth_cookies(response: Response, user: User) -> None:
    secure = cookies_secure()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=dump_session(user.id, user.email),
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
        max_age=SESSION_MAX_AGE,
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=secrets.token_urlsafe(32),
        httponly=False,
        samesite="lax",
        secure=secure,
        path="/",
        max_age=SESSION_MAX_AGE,
    )


def clear_auth_cookies(response: Response) -> None:
    secure = cookies_secure()
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="lax", secure=secure, httponly=True)
    response.delete_cookie(CSRF_COOKIE, path="/", samesite="lax", secure=secure, httponly=False)


def authenticate(session: Session, email: str, password: str, ip: str) -> User:
    if login_blocked(ip):
        raise ApiError(429, "rate_limited", "demasiados intentos; espera 15 minutos")
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        burn_password_check(password)
        record_login_failure(ip)
        raise ApiError(401, "invalid_credentials", "credenciales inválidas")
    if not verify_password(password, user.password_hash):
        record_login_failure(ip)
        raise ApiError(401, "invalid_credentials", "credenciales inválidas")
    clear_login_failures(ip)
    return user
