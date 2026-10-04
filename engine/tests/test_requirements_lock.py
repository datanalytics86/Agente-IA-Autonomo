"""requirements.txt tiene que cubrir [project].dependencies con versiones fijadas."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ENGINE_ROOT / "pyproject.toml"
REQUIREMENTS = ENGINE_ROOT / "requirements.txt"

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*")
_PIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[^\]]+\])?==\S+$")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _dist_name(spec: str) -> str:
    base = re.sub(r"\[.*?\]", "", spec.split(";", 1)[0]).strip()
    match = _NAME.match(base)
    if match is None:
        raise AssertionError(f"dependencia ilegible: {spec}")
    return _normalize(match.group(0))


def _requirement_names() -> set[str]:
    names: set[str] = set()
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not _PIN.match(line):
            raise AssertionError(f"línea sin versión fijada: {raw}")
        names.add(_dist_name(line))
    return names


def test_requirements_cubre_pyproject() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    declared = [str(item) for item in data["project"]["dependencies"]]
    pinned = _requirement_names()
    missing = [_dist_name(spec) for spec in declared if _dist_name(spec) not in pinned]
    assert not missing, "faltan en requirements.txt: " + ", ".join(missing)
    assert "psycopg" in pinned
    assert "psycopg-binary" in pinned
    assert "pyyaml" in pinned
