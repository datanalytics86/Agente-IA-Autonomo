"""CLI: servir la API, crear el admin y exportar OpenAPI."""

from __future__ import annotations

import os
import sys

from sqlalchemy import select

from api.app import create_app
from api.security import hash_password
from api.yamlutil import dump_yaml
from core.config import REPO_ROOT, reset_settings
from db.models import User
from db.session import create_all, reset_engine, session_scope


def main() -> int:
    import uvicorn

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run(create_app(), host=host, port=port)
    return 0


def create_admin() -> int:
    """Crea o rota el único admin. La contraseña sale de ADMIN_PASSWORD y no se imprime."""
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD")
    if password is None or password.strip() == "":
        print(
            "Falta ADMIN_PASSWORD. Definila en el entorno; "
            "no la escribas en un archivo de ejemplo.",
            file=sys.stderr,
        )
        return 2
    if not email:
        print("Falta ADMIN_EMAIL.", file=sys.stderr)
        return 2
    reset_settings()
    reset_engine()
    try:
        create_all()
        with session_scope() as session:
            users = list(session.scalars(select(User).order_by(User.email.asc())))
            chosen = next((row for row in users if row.email == email), None)
            if chosen is None and users:
                chosen = users[0]
            digest = hash_password(password)
            if chosen is None:
                session.add(User(email=email, password_hash=digest))
                print(f"admin creado: {email}")
            else:
                chosen.email = email
                chosen.password_hash = digest
                session.add(chosen)
                print(f"admin actualizado: {email}")
    finally:
        reset_engine()
    return 0


def export_openapi() -> int:
    app = create_app()
    schema = app.openapi()
    schema["servers"] = [{"url": "http://localhost"}]
    destination = REPO_ROOT / "docs" / "contracts" / "openapi.yaml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dump_yaml(schema), encoding="utf-8")
    print(destination)
    return 0
