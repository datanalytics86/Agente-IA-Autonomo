"""Smoke del CLI. `--mode prompts` debe salir 0. No corre `demo`.

`engine/` se inserta en `sys.path`, así que el mismo archivo pasa desde la
raíz (`python -m pytest engine/tests/test_smoke_cli.py`) y desde `engine/`
(`python -m pytest -q tests/test_smoke_cli.py`). El job de CI usa `engine/`.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))


def test_mode_prompts_sale_cero() -> None:
    import main

    assert main.main(["--mode", "prompts"]) == 0


def test_tmp_env_es_demo_sin_envio(tmp_env: dict[str, str]) -> None:
    assert tmp_env["APP_MODE"] == "demo"
    assert os.environ["DRY_RUN"] == "true"
    assert os.environ["OUTREACH_ENABLED"] == "false"
    assert os.environ["DATABASE_URL"].startswith("sqlite:///")
    assert "state/agencia.db" not in os.environ["DATABASE_URL"]


def test_block_network_permite_localhost(block_network: None) -> None:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    client = socket.socket()
    try:
        client.connect(("127.0.0.1", port))
    finally:
        client.close()
        server.close()


def test_block_network_rechaza_externo(block_network: None) -> None:
    sock = socket.socket()
    try:
        with pytest.raises(RuntimeError, match="socket externo"):
            sock.connect(("example.com", 443))
        with pytest.raises(RuntimeError, match="socket externo"):
            socket.create_connection(("1.1.1.1", 443), timeout=0.01)
    finally:
        sock.close()
