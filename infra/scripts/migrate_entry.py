"""`alembic upgrade head` y luego queda vivo.

`docker compose up --wait` trata un contenedor que sale, aunque sea con 0,
como fallo. El healthcheck pasa solo después del upgrade. Una segunda
corrida es idempotente.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import time


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode
    pathlib.Path("/tmp/migrated").write_text("ok", encoding="utf-8")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    raise SystemExit(main())
