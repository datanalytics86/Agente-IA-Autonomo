#!/usr/bin/env python3
"""Fija engine/requirements.txt desde [project].dependencies.

No edites requirements.txt a mano. Desde engine/:

    python scripts/lock.py

Usa ``pip install --dry-run --ignore-installed --report`` para resolver
el cierre transitivo sin tocar el entorno. Cada línea queda con ``==``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ENGINE_ROOT / "pyproject.toml"
REQUIREMENTS = ENGINE_ROOT / "requirements.txt"

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def project_dependencies() -> list[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]
    if not isinstance(deps, list) or not deps:
        raise SystemExit("pyproject.toml no tiene [project].dependencies")
    return [str(item) for item in deps]


def dist_name(spec: str) -> str:
    base = spec.split(";", 1)[0]
    base = re.sub(r"\[.*?\]", "", base).strip()
    match = _NAME.match(base)
    if match is None:
        raise SystemExit(f"dependencia ilegible: {spec}")
    return match.group(0)


def resolve(deps: list[str]) -> dict[str, str]:
    report = ENGINE_ROOT / ".lock-report.json"
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--dry-run",
        "--ignore-installed",
        "--report",
        str(report),
        "--disable-pip-version-check",
        *deps,
    ]
    try:
        subprocess.run(cmd, check=True, cwd=ENGINE_ROOT)
        payload = json.loads(report.read_text(encoding="utf-8"))
    finally:
        report.unlink(missing_ok=True)
    pinned: dict[str, str] = {}
    for item in payload.get("install") or []:
        meta = item.get("metadata") or {}
        name = str(meta.get("name") or "")
        version = str(meta.get("version") or "")
        if not name or not version:
            raise SystemExit(f"entrada del reporte sin nombre o versión: {item!r}")
        pinned[dist_name(name)] = version
    return pinned


def render(deps: list[str], pinned: dict[str, str]) -> str:
    missing = [
        dist_name(spec)
        for spec in deps
        if normalize(dist_name(spec)) not in {normalize(k) for k in pinned}
    ]
    if missing:
        raise SystemExit("el resolver no cubrió: " + ", ".join(missing))
    wanted = {normalize(dist_name(spec)): spec for spec in deps}
    lines: list[str] = []
    for name in sorted(pinned, key=str.casefold):
        version = pinned[name]
        spec = wanted.get(normalize(name))
        if spec is not None and "[" in spec.split(";", 1)[0]:
            extra = spec.split(";", 1)[0]
            bracket = extra[extra.index("[") : extra.index("]") + 1]
            lines.append(f"{name}{bracket}=={version}")
        else:
            lines.append(f"{name}=={version}")
    header = (
        "# Generado por engine/scripts/lock.py. No editar a mano.\n"
        "# Versiones fijadas de [project].dependencies y sus transitivas.\n"
    )
    return header + "\n".join(lines) + "\n"


def main() -> int:
    deps = project_dependencies()
    pinned = resolve(deps)
    REQUIREMENTS.write_text(render(deps, pinned), encoding="utf-8", newline="\n")
    print(REQUIREMENTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
