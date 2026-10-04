"""Errores JSON `{"error": {"code", "message", "details"}}`."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from core.errors import DuplicateLeadError, TransitionError

logger = logging.getLogger("api")


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _validation_items(exc: RequestValidationError) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for err in exc.errors():
        items.append(
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
        )
    return items


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error",
                "datos inválidos",
                {"errors": _validation_items(exc)},
            ),
        )

    @app.exception_handler(HTTPException)
    async def _http(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            details = exc.detail.get("details")
            extra = details if isinstance(details, dict) else {}
            return JSONResponse(
                status_code=exc.status_code,
                content=error_body(
                    str(exc.detail.get("code")),
                    str(exc.detail.get("message", "")),
                    extra,
                ),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(f"http_{exc.status_code}", str(exc.detail)),
        )

    @app.exception_handler(TransitionError)
    async def _transition(_request: Request, exc: TransitionError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=error_body("transition_error", str(exc)),
        )

    @app.exception_handler(DuplicateLeadError)
    async def _duplicate(_request: Request, exc: DuplicateLeadError) -> JSONResponse:
        return JSONResponse(status_code=409, content=error_body("duplicate_lead", str(exc)))

    @app.exception_handler(IntegrityError)
    async def _integrity(_request: Request, _exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=error_body("conflict", "el registro choca con uno existente"),
        )

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("error no controlado")
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "error interno", {"type": type(exc).__name__}),
        )
