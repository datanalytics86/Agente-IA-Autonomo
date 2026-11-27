"""CLI de simulación. `main(days, seed)` es el modo simulate."""

from __future__ import annotations

import argparse

from simulation.loop import run_simulation


def main(days: int = 14, seed: int = 42) -> int:
    return run_simulation(days=days, seed=seed)


def cli(argv: list[str] | None = None) -> int:
    """`python -m simulation.cli --days N`. Sin flags conserva los 14 días."""
    parser = argparse.ArgumentParser(prog="python -m simulation.cli")
    parser.add_argument("--days", type=int, default=14)
    args, _unknown = parser.parse_known_args(argv)
    if args.days < 1:
        parser.error("--days debe ser un entero >= 1")
    return main(days=args.days)


if __name__ == "__main__":
    raise SystemExit(cli())
