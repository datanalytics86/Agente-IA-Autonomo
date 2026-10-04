"""Horario America/Santiago, feriados de Chile y días hábiles."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import holidays

from core.config import get_settings

SEND_WINDOWS: tuple[tuple[int, int], ...] = (
    (9 * 60 + 30, 13 * 60),
    (15 * 60, 18 * 60 + 30),
)


def zone() -> ZoneInfo:
    name = get_settings().tz or "America/Santiago"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def chile_holidays() -> holidays.HolidayBase:
    """País CL, sin subdivisión: el paquete no la fija de forma estable."""
    return holidays.country_holidays("CL")


def to_local(moment: datetime) -> datetime:
    current = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return current.astimezone(zone())


def is_business_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    return day not in chile_holidays()


def in_send_window(moment: datetime) -> bool:
    local = to_local(moment)
    if not is_business_day(local.date()):
        return False
    minutes = local.hour * 60 + local.minute
    return any(start <= minutes < end for start, end in SEND_WINDOWS)


def next_window_open(moment: datetime) -> datetime:
    """Próximo instante hábil dentro de la ventana. Si ya está dentro, lo devuelve."""
    local = to_local(moment)
    tz = zone()
    for offset in range(21):
        day = (local + timedelta(days=offset)).date()
        if not is_business_day(day):
            continue
        base = datetime(day.year, day.month, day.day, tzinfo=tz)
        windows = tuple(
            (base + timedelta(minutes=start), base + timedelta(minutes=end))
            for start, end in SEND_WINDOWS
        )
        anchor = local if offset == 0 else base
        for start, end in windows:
            if offset == 0 and start <= anchor < end:
                return anchor.astimezone(UTC)
            if anchor <= start:
                return start.astimezone(UTC)
    raise RuntimeError("no hay ventana de envío en 21 días")


def after_jitter(moment: datetime, minutes: int) -> datetime:
    """Suma el jitter y, si se sale, cae al inicio de la siguiente ventana."""
    candidate = moment + timedelta(minutes=minutes)
    if in_send_window(candidate):
        return candidate
    return next_window_open(candidate)


def jitter_minutes(rng: random.Random, *, real: bool) -> int:
    """2–7 min. Reloj real: entropía del sistema. Simulación: RNG con semilla."""
    if real:
        return random.SystemRandom().randint(2, 7)
    return rng.randint(2, 7)


def add_business_days(day: date, count: int) -> date:
    current = day
    left = count
    while left > 0:
        current += timedelta(days=1)
        if is_business_day(current):
            left -= 1
    return current


def start_of_local_day(moment: datetime) -> datetime:
    local = to_local(moment)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


def local_date(moment: datetime) -> date:
    return to_local(moment).date()
