"""Lectura de headers HTTP sin depender de la capitalización."""

from __future__ import annotations

from collections.abc import Mapping


def header(headers: Mapping[str, str], name: str) -> str:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return str(value).strip()
    return ""
