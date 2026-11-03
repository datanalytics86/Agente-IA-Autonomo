"""Login. El resto de auth vive en el router admin (sesión + CSRF)."""

from __future__ import annotations

from fastapi import APIRouter, Response

from api.deps import Db, apply_auth_cookies, authenticate
from api.schemas import LoginIn, UserOut
from db.models import utcnow

router = APIRouter(tags=["admin"])


@router.post("/api/auth/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, session: Db) -> UserOut:
    user = authenticate(
        session,
        payload.email,
        payload.password,
        payload.email.strip().lower(),
    )
    user.last_login_at = utcnow()
    session.add(user)
    session.flush()
    apply_auth_cookies(response, user)
    return UserOut(email=user.email)
