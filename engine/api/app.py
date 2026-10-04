"""Aplicación FastAPI."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from api.deps import build_payment_provider
from api.errors import register_exception_handlers
from api.log import configure_logging
from api.routers import admin, auth, health, internal, public, webhooks
from core.config import get_settings
from db.session import create_all, reset_engine

logger = logging.getLogger("api.access")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    reset_engine()
    create_all()
    app.state.payment_provider = build_payment_provider(get_settings())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Agencia API",
        version="0.1.0",
        description=(
            "API de la agencia. JSON en snake_case. "
            "Los errores usan el esquema Error. Regenerada desde FastAPI."
        ),
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origin_list),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def access_log(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        logger.info("%s %s %s", request.method, path, response.status_code)
        return response

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(public.router)
    app.include_router(webhooks.router)
    app.include_router(internal.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    return app
