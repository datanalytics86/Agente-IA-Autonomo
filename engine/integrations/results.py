"""Resultado de un envío. `blocked` no salió a la red."""

from __future__ import annotations

from pydantic import BaseModel


class SendResult(BaseModel):
    status: str
    provider_message_id: str | None = None
    reason: str = ""
    channel: str = ""
