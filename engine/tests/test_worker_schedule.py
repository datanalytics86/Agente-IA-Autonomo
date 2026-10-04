"""Ventanas, feriados y jitter determinista."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from worker.schedule import (
    add_business_days,
    after_jitter,
    in_send_window,
    is_business_day,
    jitter_minutes,
    zone,
)

TZ = ZoneInfo("America/Santiago")


def _at(day: str, hour: int, minute: int) -> datetime:
    year, month, dom = (int(part) for part in day.split("-"))
    return datetime(year, month, dom, hour, minute, tzinfo=TZ)


def test_ventana_lunes_a_viernes() -> None:
    assert in_send_window(_at("2026-03-03", 9, 30))
    assert in_send_window(_at("2026-03-03", 12, 59))
    assert in_send_window(_at("2026-03-03", 15, 0))
    assert in_send_window(_at("2026-03-03", 18, 29))
    assert not in_send_window(_at("2026-03-03", 9, 29))
    assert not in_send_window(_at("2026-03-03", 13, 0))
    assert not in_send_window(_at("2026-03-03", 14, 30))
    assert not in_send_window(_at("2026-03-03", 18, 30))
    assert not in_send_window(_at("2026-03-07", 10, 0))
    assert not in_send_window(_at("2026-03-08", 10, 0))


def test_feriado_chileno_no_es_ventana() -> None:
    assert not is_business_day(date(2026, 9, 18))
    assert not in_send_window(_at("2026-09-18", 10, 0))
    assert not in_send_window(_at("2026-01-01", 11, 0))


def test_dias_habiles_saltan_fin_de_semana_y_feriado() -> None:
    assert add_business_days(date(2026, 3, 2), 4) == date(2026, 3, 6)
    assert add_business_days(date(2026, 3, 6), 1) == date(2026, 3, 9)
    assert add_business_days(date(2026, 4, 2), 1) == date(2026, 4, 6)


def test_jitter_de_simulacion_queda_en_la_ventana() -> None:
    rng = random.Random(42)
    moment = _at("2026-03-03", 12, 50)
    for _ in range(30):
        minutes = jitter_minutes(rng, real=False)
        assert 2 <= minutes <= 7
        landed = after_jitter(moment, minutes)
        assert in_send_window(landed)
        assert landed.tzinfo is not None
    late = after_jitter(_at("2026-03-03", 18, 28), 7)
    assert in_send_window(late)
    assert late > _at("2026-03-03", 18, 28)


def test_zona_por_defecto() -> None:
    assert str(zone()) == "America/Santiago"
    assert after_jitter(_at("2026-03-03", 10, 0), 5) - _at("2026-03-03", 10, 0) == timedelta(
        minutes=5
    )
