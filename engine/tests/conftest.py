"""Fixtures de QA. `block_network` no es autouse: no rompe la colección."""

from __future__ import annotations

import ipaddress
import json
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

_ENV_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "env_demo.json"
_DEMO_FLAGS = {
    "APP_MODE": "demo",
    "DRY_RUN": "true",
    "OUTREACH_ENABLED": "false",
}


def _host_from_address(address: object) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    if isinstance(address, str):
        return address
    return None


def _allows(host: str) -> bool:
    bare = host.strip().strip("[]").split("%", 1)[0]
    if bare.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(bare).is_loopback
    except ValueError:
        return False


def _reject(host: str) -> None:
    raise RuntimeError(f"socket externo bloqueado en tests: {host}")


@pytest.fixture
def tmp_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    """Fija demo, dry-run y sqlite temporal. No toca `engine/state/`."""
    payload = json.loads(_ENV_FIXTURE.read_text(encoding="utf-8"))
    values = {
        "APP_MODE": str(payload["APP_MODE"]),
        "DRY_RUN": str(payload["DRY_RUN"]),
        "OUTREACH_ENABLED": str(payload["OUTREACH_ENABLED"]),
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'agencia.db').as_posix()}",
    }
    for key, expected in _DEMO_FLAGS.items():
        if values[key] != expected:
            raise AssertionError(f"{key} debe ser {expected} en tests")
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


@pytest.fixture
def block_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Falla si se abre un socket que no sea loopback. No es autouse."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection

    def connect(self: socket.socket, address: object) -> None:
        host = _host_from_address(address)
        if host is None or not _allows(host):
            _reject(host or repr(address))
        real_connect(self, address)  # type: ignore[arg-type]

    def connect_ex(self: socket.socket, address: object) -> int:
        host = _host_from_address(address)
        if host is None or not _allows(host):
            _reject(host or repr(address))
        return real_connect_ex(self, address)  # type: ignore[arg-type]

    def create_connection(address: object, *args: object, **kwargs: object) -> socket.socket:
        host = _host_from_address(address)
        if host is None or not _allows(host):
            _reject(host or repr(address))
        return real_create_connection(address, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    yield
