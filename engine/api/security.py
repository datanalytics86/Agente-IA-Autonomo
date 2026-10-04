"""Sesión, CSRF, argon2, firmas de webhooks y Turnstile."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer

from api.errors import ApiError
from core.config import get_settings

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"
SESSION_MAX_AGE = 60 * 60 * 24 * 7
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 5
_TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

_HASHER = PasswordHasher()
_DUMMY_HASH = _HASHER.hash("not-a-real-password")
_login_failures: dict[str, list[float]] = {}


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bool(_HASHER.verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    """Iguala el costo de argon2 cuando el email no existe."""
    verify_password(password, _DUMMY_HASH)


def reset_login_attempts() -> None:
    _login_failures.clear()


def login_blocked(ip: str) -> bool:
    moment = time.monotonic()
    recent = [item for item in _login_failures.get(ip, []) if moment - item < _LOGIN_WINDOW_SECONDS]
    _login_failures[ip] = recent
    return len(recent) >= _LOGIN_MAX_FAILURES


def record_login_failure(ip: str) -> None:
    moment = time.monotonic()
    recent = [item for item in _login_failures.get(ip, []) if moment - item < _LOGIN_WINDOW_SECONDS]
    recent.append(moment)
    _login_failures[ip] = recent


def clear_login_failures(ip: str) -> None:
    _login_failures.pop(ip, None)


def cookies_secure() -> bool:
    return get_settings().public_base_url.lower().startswith("https://")


def _session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().resolved_secret_key, salt="agencia-session")


def dump_session(user_id: str, email: str) -> str:
    return str(_session_serializer().dumps({"uid": user_id, "email": email}))


def load_session(token: str) -> dict[str, str]:
    try:
        data = _session_serializer().loads(token, max_age=SESSION_MAX_AGE)
    except SignatureExpired as exc:
        raise ApiError(401, "unauthenticated", "sesión vencida") from exc
    except BadSignature as exc:
        raise ApiError(401, "unauthenticated", "sesión inválida") from exc
    if not isinstance(data, dict) or not data.get("uid"):
        raise ApiError(401, "unauthenticated", "sesión inválida")
    return {"uid": str(data["uid"]), "email": str(data.get("email", ""))}


def _baja_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().resolved_secret_key, salt="baja")


def make_baja_token(lead_id: str) -> str:
    return str(_baja_serializer().dumps({"lead_id": lead_id}))


def read_baja_token(token: str) -> str:
    try:
        data = _baja_serializer().loads(token)
    except BadSignature as exc:
        raise ApiError(400, "invalid_token", "token de baja inválido") from exc
    if not isinstance(data, dict) or not data.get("lead_id"):
        raise ApiError(400, "invalid_token", "token de baja inválido")
    return str(data["lead_id"])


def hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def text_version(text: str) -> str:
    digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]
    return f"sha256:{digest}"


def consent_record(kind: str, version: str, ip: str) -> dict[str, str]:
    return {
        "type": kind,
        "text_version": version,
        "ts": datetime.now(UTC).isoformat(),
        "ip_hash": hash_ip(ip),
    }


def turnstile_accepts(token: str, remote_ip: str | None) -> bool:
    """Sin secret: demo acepta y prod rechaza. Con secret, Cloudflare decide."""
    settings = get_settings()
    secret = settings.turnstile_secret_key.strip()
    if secret == "":
        return settings.app_mode == "demo"
    if token.strip() == "":
        return False
    try:
        response = httpx.post(
            _TURNSTILE_URL,
            data={"secret": secret, "response": token, "remoteip": remote_ip or ""},
            timeout=5.0,
            follow_redirects=False,
        )
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("success") is True


def mp_payment_id(body: bytes, query_id: str | None) -> str:
    if query_id and query_id.strip():
        return query_id.strip()
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("webhook sin id") from exc
    if not isinstance(payload, dict):
        raise ValueError("webhook sin id")
    data = payload.get("data")
    if isinstance(data, dict) and data.get("id") is not None:
        return str(data["id"])
    if payload.get("id") is not None:
        return str(payload["id"])
    raise ValueError("webhook sin id")


def _mp_manifest(data_id: str, request_id: str, ts: str) -> bytes:
    signed = data_id.lower() if data_id.isalnum() else data_id
    return f"id:{signed};request-id:{request_id};ts:{ts};".encode()


def mercadopago_signature(secret: str, data_id: str, request_id: str, ts: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        _mp_manifest(data_id, request_id, ts),
        hashlib.sha256,
    ).hexdigest()
    return f"ts={ts},v1={digest}"


def _header_parts(header: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for chunk in header.split(","):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts[key.strip()] = value.strip()
    return parts


def _same(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def verify_mercadopago(
    secret: str,
    body: bytes,
    headers: Mapping[str, str],
    query_id: str | None,
) -> str:
    if not secret.strip():
        raise ApiError(401, "invalid_signature", "firma inválida")
    parts = _header_parts(headers.get("x-signature", ""))
    ts = parts.get("ts", "")
    provided = parts.get("v1", "")
    request_id = headers.get("x-request-id", "")
    if not ts or not provided or not request_id:
        raise ApiError(401, "invalid_signature", "firma inválida")
    try:
        data_id = mp_payment_id(body, query_id)
    except ValueError as exc:
        raise ApiError(401, "invalid_signature", "firma inválida") from exc
    expected = hmac.new(
        secret.encode("utf-8"),
        _mp_manifest(data_id, request_id, ts),
        hashlib.sha256,
    ).hexdigest()
    if not _same(expected, provided):
        raise ApiError(401, "invalid_signature", "firma inválida")
    return data_id


def verify_calcom(secret: str, body: bytes, header: str) -> bool:
    if not secret.strip() or not header.strip():
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = header.strip().removeprefix("sha256=")
    return _same(expected, provided)


def verify_calendly(secret: str, body: bytes, header: str) -> bool:
    if not secret.strip() or not header.strip():
        return False
    parts = _header_parts(header)
    ts = parts.get("t", "")
    provided = parts.get("v1", "")
    if not ts or not provided:
        return False
    signed = f"{ts}.".encode() + body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return _same(expected, provided)


def _svix_key(secret: str) -> bytes:
    raw = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error):
        return secret.encode("utf-8")
    return decoded or secret.encode("utf-8")


def verify_svix(secret: str, body: bytes, headers: Mapping[str, str]) -> bool:
    if not secret.strip():
        return False
    message_id = headers.get("svix-id") or headers.get("webhook-id") or ""
    timestamp = headers.get("svix-timestamp") or headers.get("webhook-timestamp") or ""
    signature = headers.get("svix-signature") or headers.get("webhook-signature") or ""
    if not message_id or not timestamp or not signature:
        return False
    signed = f"{message_id}.{timestamp}.".encode() + body
    digest = hmac.new(_svix_key(secret), signed, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    for part in signature.split():
        version, _, value = part.partition(",")
        if version == "v1" and _same(expected, value):
            return True
    return False


def verify_meta(secret: str, body: bytes, header: str) -> bool:
    if not secret.strip() or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return _same(expected, header)
