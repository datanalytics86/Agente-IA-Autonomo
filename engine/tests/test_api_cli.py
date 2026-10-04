"""CLI create-admin. La contraseña solo vive en el entorno del test."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from api.cli import create_admin
from api.security import verify_password
from core.config import reset_settings
from db.models import User
from db.session import reset_engine, session_scope

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _caches() -> object:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


def test_create_admin_sin_password_sale_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'cli.db').as_posix()}")
    assert create_admin() == 2


def test_create_admin_sin_email_sale_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "una-clave-temporal")
    monkeypatch.setenv("ADMIN_EMAIL", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'cli.db').as_posix()}")
    assert create_admin() == 2


def test_create_admin_crea_y_rota(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'cli.db').as_posix()}")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "una-clave-temporal")
    assert create_admin() == 0
    monkeypatch.setenv("ADMIN_PASSWORD", "otra-clave-temporal")
    assert create_admin() == 0
    with session_scope() as session:
        users = list(session.scalars(select(User)))
        assert len(users) == 1
        assert users[0].email == "admin@example.com"
        assert verify_password("otra-clave-temporal", users[0].password_hash)
        assert users[0].password_hash.startswith("$argon2")


def test_ejemplo_no_guarda_admin_password() -> None:
    for relative in (".env.example", "engine/.env.example"):
        text = (_ROOT / relative).read_text(encoding="utf-8")
        assert "ADMIN_PASSWORD=" not in text
