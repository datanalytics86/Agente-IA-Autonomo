#!/usr/bin/env python3
"""Agente IA Autónomo — CLI multiagente (landing pages para pymes Chile)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Asegurar imports desde raíz del proyecto
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from agents.base import (  # noqa: E402
    Lead,
    ensure_state_dirs,
    list_prompts,
    load_leads,
    load_logs,
    read_prompt,
    status_counts,
)
from agents.pipeline import Orchestrator  # noqa: E402
from agents.scout import run_scout  # noqa: E402

console = Console()


def print_banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Agente IA Autónomo[/bold cyan]\n"
            "[dim]Multiagente · landings para pymes locales (Chile) · modo DEMO[/dim]",
            border_style="cyan",
        )
    )


def table_status_counts(counts: dict[str, int]) -> Table:
    table = Table(title="Leads por status", show_header=True, header_style="bold magenta")
    table.add_column("Status", style="cyan")
    table.add_column("Cantidad", justify="right", style="green")
    total = 0
    for status, n in counts.items():
        if n > 0:
            table.add_row(status, str(n))
            total += n
    table.add_row("[bold]total[/bold]", f"[bold]{total}[/bold]")
    return table


def table_leads(leads: list[Lead]) -> Table:
    table = Table(title="Leads", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", max_width=16)
    table.add_column("Negocio")
    table.add_column("Comuna")
    table.add_column("Status", style="cyan")
    table.add_column("CLP", justify="right")
    table.add_column("HV", justify="center")
    for lead in leads:
        table.add_row(
            lead.id[-12:],
            lead.business[:28],
            lead.commune,
            lead.status.value,
            f"{lead.estimated_value_clp:,}".replace(",", "."),
            "⚠" if lead.high_value or lead.status.value == "revision" else "",
        )
    return table


def print_logs(limit: int = 12) -> None:
    logs = load_logs(limit=limit)
    table = Table(title=f"Últimos logs ({len(logs)})", show_header=True, header_style="bold yellow")
    table.add_column("Ts", style="dim", max_width=22)
    table.add_column("Agente", style="cyan")
    table.add_column("Mensaje")
    for entry in logs:
        table.add_row(
            str(entry.get("ts", ""))[:19],
            str(entry.get("agent", "")),
            str(entry.get("message", ""))[:90],
        )
    console.print(table)


def cmd_demo() -> int:
    print_banner()
    ensure_state_dirs()
    orch = Orchestrator()
    result = orch.run_demo(scout_count=3, simulate_reply=False)

    console.print("\n[bold green]✓ Ciclo DEMO completado[/bold green]\n")
    console.print(table_status_counts(result.counts))
    console.print()
    console.print(table_leads(load_leads()))
    console.print()
    print_logs(15)

    # Resumen artefactos
    landings = list((ROOT / "output").glob("*.html"))
    boards = list((ROOT / "output").glob("storyboard_*.md"))
    console.print(
        Panel(
            f"Scout: {len(result.scouted)} leads\n"
            f"Diagnoser: {len(result.diagnosed)} · Builder: {len(result.built)} · "
            f"Filmer: {len(result.filmed)}\n"
            f"Checker: {len(result.checked)} · Pitcher: {len(result.pitched)}\n"
            f"HTML en output/: {len(landings)} · Storyboards: {len(boards)}\n"
            f"[yellow]High-value → status revision (HITL, sin envío automático)[/yellow]",
            title="Resumen",
            border_style="green",
        )
    )
    return 0


def cmd_status() -> int:
    print_banner()
    ensure_state_dirs()
    leads = load_leads()
    counts = status_counts()
    console.print(table_status_counts(counts))
    console.print()
    if leads:
        console.print(table_leads(leads))
    else:
        console.print("[dim]No hay leads. Corre: python main.py --mode demo[/dim]")
    console.print()
    print_logs(15)
    return 0


def cmd_scout() -> int:
    print_banner()
    ensure_state_dirs()
    leads = run_scout(count=3, force_high_value=True)
    console.print(f"[green]Scout creó {len(leads)} leads[/green]")
    console.print(table_leads(leads))
    print_logs(8)
    return 0


def cmd_cycle() -> int:
    print_banner()
    ensure_state_dirs()
    orch = Orchestrator()
    result = orch.run_cycle()
    console.print("[bold green]✓ Ciclo completo[/bold green]")
    console.print(table_status_counts(result.counts))
    console.print()
    console.print(table_leads(load_leads()))
    console.print()
    print_logs(15)
    return 0


def cmd_prompts() -> int:
    print_banner()
    names = list_prompts()
    table = Table(title="Prompts disponibles", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("Archivo")
    table.add_column("Líneas", justify="right")
    for i, name in enumerate(names, 1):
        text = read_prompt(name.replace(".md", ""))
        table.add_row(str(i), name, str(len(text.splitlines())))
    console.print(table)
    if not names:
        console.print("[red]No se encontraron prompts en prompts/[/red]")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Agente IA Autónomo — sistema multiagente para vender landings a pymes en Chile",
    )
    parser.add_argument(
        "--mode",
        choices=["demo", "status", "scout", "cycle", "prompts"],
        default="demo",
        help="Modo de ejecución (default: demo)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "demo": cmd_demo,
        "status": cmd_status,
        "scout": cmd_scout,
        "cycle": cmd_cycle,
        "prompts": cmd_prompts,
    }
    try:
        return handlers[args.mode]()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrumpido[/yellow]")
        return 130
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
