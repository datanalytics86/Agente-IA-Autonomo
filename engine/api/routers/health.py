"""Proceso vivo y base alcanzable."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.errors import error_body
from db.session import get_engine

router = APIRouter(tags=["public"])
logger = logging.getLogger("api.health")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
def readyz() -> JSONResponse | dict[str, str]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("readyz sin base")
        return JSONResponse(
            status_code=503,
            content=error_body("not_ready", "base de datos no disponible"),
        )
    return {"status": "ok"}
