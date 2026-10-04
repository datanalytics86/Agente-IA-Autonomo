"""Volcado YAML mínimo para el OpenAPI. Solo tipos JSON."""

from __future__ import annotations

import json
from typing import Any


def dump_yaml(value: Any) -> str:
    plain = json.loads(json.dumps(value, ensure_ascii=False, default=str))
    lines: list[str] = []
    _dump(plain, lines, 0)
    return "\n".join(lines) + "\n"


def _inline(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict) and not value:
        return "{}"
    if isinstance(value, list) and not value:
        return "[]"
    return json.dumps(value, ensure_ascii=False)


def _dump(value: Any, lines: list[str], indent: int) -> None:
    pad = "  " * indent
    if isinstance(value, dict):
        if not value:
            lines.append(f"{pad}{{}}")
            return
        for key, item in value.items():
            rendered = json.dumps(str(key), ensure_ascii=False)
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}{rendered}:")
                _dump(item, lines, indent + 1)
            else:
                lines.append(f"{pad}{rendered}: {_inline(item)}")
        return
    if isinstance(value, list):
        if not value:
            lines.append(f"{pad}[]")
            return
        for item in value:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}-")
                _dump(item, lines, indent + 1)
            else:
                lines.append(f"{pad}- {_inline(item)}")
        return
    lines.append(f"{pad}{_inline(value)}")
