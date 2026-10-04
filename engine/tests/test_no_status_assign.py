"""Falla si alguien asigna .status fuera de core y agents."""

from __future__ import annotations

import os
import re
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
ALLOWED = (ENGINE / "core", ENGINE / "agents")
SKIP_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}
PATTERN = re.compile(r"\.status\s*=(?!=)")


def _python_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames if name not in SKIP_DIRS and not name.endswith(".egg-info")
        ]
        for filename in filenames:
            if filename.endswith(".py"):
                found.append(Path(dirpath) / filename)
    return found


def test_no_hay_asignacion_de_status_fuera_de_core_y_agents() -> None:
    offenders: list[str] = []
    for path in _python_files(ENGINE):
        if any(path.resolve().is_relative_to(folder) for folder in ALLOWED):
            continue
        text = path.read_text(encoding="utf-8")
        for match in PATTERN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            snippet = text.splitlines()[line_no - 1].strip()
            offenders.append(f"{path.relative_to(ENGINE)}:{line_no}: {snippet}")
    assert offenders == []
