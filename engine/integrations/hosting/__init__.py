"""Hosting de sitios de clientes. Caddy es el default."""

from integrations.hosting.base import (
    CaddyHosting,
    CloudflarePagesHosting,
    FakeHosting,
    SiteHosting,
    build_hosting,
    normalize_host,
    project_slug,
)

__all__ = [
    "CaddyHosting",
    "CloudflarePagesHosting",
    "FakeHosting",
    "SiteHosting",
    "build_hosting",
    "normalize_host",
    "project_slug",
]
