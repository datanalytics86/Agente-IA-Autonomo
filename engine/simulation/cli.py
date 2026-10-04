"""CLI de simulación. `main(days, seed)` es el modo simulate."""

from __future__ import annotations

from simulation.loop import run_simulation


def main(days: int = 14, seed: int = 42) -> int:
    return run_simulation(days=days, seed=seed)
