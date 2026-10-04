"""Escaneo local de secretos. No abre sockets ni lee el entorno."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
SKIP_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
}
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".astro",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".html",
    ".css",
    ".txt",
    ".example",
    ".sql",
    ".ini",
    ".cfg",
}
BARE_NAMES = {"dockerfile", "caddyfile", ".env", ".env.example"}
PATTERNS = (
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("github-fine-grained", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    (
        "private-key",
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    ),
    ("openai-style", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{20,}")),
    ("xai-key", re.compile(r"(?<![A-Za-z0-9])xai-[A-Za-z0-9]{20,}")),
)


def _scannable(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    if path.resolve() == SELF:
        return False
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name.lower() in BARE_NAMES


def test_el_arbol_no_contiene_secretos() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or not _scannable(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for name, pattern in PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{name}: {relative}:{line}")
    assert hits == []
