"""Deja un job_run al arrancar y después corre el scheduler.

El intervalo más corto del worker es 5 minutos. El smoke exige un `job_runs`
en menos de 2 minutos: `metrics_rollup` solo lee y escribe un setting.
"""

from __future__ import annotations


def _prime() -> None:
    from worker.scheduler import run_job

    run_job("metrics_rollup")


def main() -> int:
    _prime()
    from worker.cli import main as worker_main

    return worker_main()


if __name__ == "__main__":
    raise SystemExit(main())
