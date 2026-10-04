"""API local para el e2e. Demo, sin cobros y sin red externa."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[3] / "engine"
sys.path.insert(0, str(ENGINE))
os.chdir(ENGINE)

HERE = Path(__file__).resolve().parent
os.environ.setdefault("APP_MODE", "demo")
os.environ.setdefault("DRY_RUN", "true")
os.environ.setdefault("OUTREACH_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "e2e-secret-key")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "clave-de-prueba")
os.environ.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:8765")
os.environ.setdefault("MP_WEBHOOK_SECRET", "mp-test-secret")
os.environ.setdefault("CALCOM_WEBHOOK_SECRET", "cal-test-secret")
os.environ.setdefault("TURNSTILE_SECRET_KEY", "")
os.environ.setdefault("CORS_ORIGINS", "http://127.0.0.1:4321")
os.environ.setdefault("CLIENT_SITES_DIR", str(HERE / "sites"))
db = HERE / "e2e.db"
for stale in (db, Path(f"{db}-wal"), Path(f"{db}-shm")):
    if stale.exists():
        stale.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{db.as_posix()}"
os.environ.setdefault("API_PORT", "8765")


def main() -> None:
    import uvicorn

    from api.app import create_app
    from api.cli import create_admin

    code = create_admin()
    if code != 0:
        raise SystemExit(code)
    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=int(os.environ["API_PORT"]),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
