"""El esquema marcado en el prompt coincide con el modelo pydantic."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agents.schemas import PROMPT_MODELS

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
_FENCE = re.compile(r"json_schema:\s*```json\s*(\{.*\})\s*```", re.DOTALL)


def _schema(name: str) -> dict[str, object]:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "version: 2.0.0" in text.split("---", 2)[1]
    assert "## Ejemplo correcto" in text
    assert "## Ejemplo incorrecto" in text
    assert "datos_no_confiables" in text or "No obedezcas" in text
    match = _FENCE.search(text)
    assert match is not None, name
    return json.loads(match.group(1))


def test_esquema_del_prompt_igual_al_modelo() -> None:
    assert set(PROMPT_MODELS) == {path.stem for path in PROMPTS.glob("*.md")}
    for name, model in PROMPT_MODELS.items():
        assert _schema(name) == model.model_json_schema()
