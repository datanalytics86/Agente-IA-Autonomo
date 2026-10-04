"""Simulación seed 42: cero violaciones, cero sockets y el mismo informe."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import reset_settings
from db.session import reset_engine
from simulation.cli import main
from simulation.loop import run_simulation
from simulation.providers import roll_intent


@pytest.fixture(autouse=True)
def _caches() -> object:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


def _url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_distribucion_inbound_esta_en_el_rango() -> None:
    import random

    rng = random.Random(42)
    total = 4000
    counts = {name: 0 for _weight, name in ()}
    silence = 0
    for _ in range(total):
        intent = roll_intent(rng)
        if intent is None:
            silence += 1
        else:
            counts[intent] = counts.get(intent, 0) + 1
    assert counts["interesado"] / total == pytest.approx(0.06, abs=0.02)
    assert counts["pregunta_precio"] / total == pytest.approx(0.03, abs=0.015)
    assert counts["opt_out"] / total == pytest.approx(0.02, abs=0.015)
    assert counts["prompt_injection"] / total == pytest.approx(0.01, abs=0.01)
    assert silence / total == pytest.approx(0.86, abs=0.03)


def test_simulacion_no_abre_sockets(block_network: None, tmp_path: Path) -> None:
    report = tmp_path / "reporte_seed42_d3.md"
    code = run_simulation(
        days=3,
        seed=42,
        report_path=report,
        database_url=_url(tmp_path / "sim3.db"),
    )
    text = report.read_text(encoding="utf-8")
    assert code == 0, text
    assert "violaciones: 0" in text


def test_tres_dias_es_determinista(tmp_path: Path) -> None:
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    url = _url(tmp_path / "det.db")
    assert run_simulation(days=3, seed=42, report_path=first, database_url=url) == 0
    assert run_simulation(days=3, seed=42, report_path=second, database_url=url) == 0
    assert first.read_bytes() == second.read_bytes()


def test_catorce_dias_seed_42_sin_violaciones(tmp_path: Path) -> None:
    report = tmp_path / "reporte_seed42_d14.md"
    code = run_simulation(
        days=14,
        seed=42,
        report_path=report,
        database_url=_url(tmp_path / "sim14.db"),
    )
    text = report.read_text(encoding="utf-8")
    assert code == 0, text
    assert "violaciones: 0" in text
    canonical = main(days=14, seed=42)
    assert canonical == 0


def test_main_firma_days_y_seed() -> None:
    import inspect

    signature = inspect.signature(main)
    assert "days" in signature.parameters
    assert "seed" in signature.parameters
