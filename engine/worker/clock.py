"""Reloj inyectable. El real usa UTC; la simulación avanza el falso sin dormir."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    @property
    def is_real(self) -> bool: ...


class SystemClock:
    @property
    def is_real(self) -> bool:
        return True

    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    def __init__(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ValueError("el reloj falso exige datetime con zona")
        self._now = moment.astimezone(UTC)

    @property
    def is_real(self) -> bool:
        return False

    def now(self) -> datetime:
        return self._now

    def advance_to(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ValueError("el reloj falso exige datetime con zona")
        target = moment.astimezone(UTC)
        if target < self._now:
            raise ValueError("el reloj falso no retrocede")
        self._now = target
