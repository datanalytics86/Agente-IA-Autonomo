"""Contexto y resultado de un agente."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


class AgentContext:
    """Sesión y parámetros de una corrida. La sesión la cierra quien la abrió."""

    def __init__(
        self,
        session: Session,
        *,
        lead_id: str | None = None,
        message_id: str | None = None,
        count: int = 1,
        force_high_value: bool = False,
        simulate_reply: bool = False,
    ) -> None:
        self.session = session
        self.lead_id = lead_id
        self.message_id = message_id
        self.count = count
        self.force_high_value = force_high_value
        self.simulate_reply = simulate_reply


class AgentResult(BaseModel):
    lead_id: str | None = None
    ok: bool
    events: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
