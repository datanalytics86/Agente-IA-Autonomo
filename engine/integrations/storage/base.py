"""Artefactos en disco bajo engine/output. No hay S3 en esta versión."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from core.config import ENGINE_DIR, Settings


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str: ...

    def get(self, key: str) -> bytes: ...


def _resolve(root: Path, key: str) -> Path:
    pure = Path(key)
    parts = pure.parts
    if (
        not key
        or pure.is_absolute()
        or ".." in parts
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("clave de storage inválida")
    if "\\" in key:
        raise ValueError("clave de storage inválida")
    base = root.resolve()
    path = base.joinpath(*parts).resolve()
    if path != base and base not in path.parents:
        raise ValueError("clave de storage inválida")
    return path


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        del content_type
        path = _resolve(self.root, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def get(self, key: str) -> bytes:
        path = _resolve(self.root, key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        del content_type
        _resolve(Path("/storage"), key)
        self.objects[key] = data
        return f"fake://{key}"

    def get(self, key: str) -> bytes:
        _resolve(Path("/storage"), key)
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]


def build_storage(settings: Settings, *, root: Path | None = None) -> ObjectStorage:
    if settings.app_mode == "demo" or settings.dry_run:
        return FakeStorage()
    return LocalStorage(root or (ENGINE_DIR / "output"))
