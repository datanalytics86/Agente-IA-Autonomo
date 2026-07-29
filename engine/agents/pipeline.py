"""Orchestrator / pipeline — coordina agentes, prioriza, HITL, logs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from agents.base import (
    HIGH_VALUE_CLP,
    Lead,
    LeadStatus,
    StateManager,
    ensure_state_dirs,
    load_leads,
    log_event,
    read_prompt,
    status_counts,
    upsert_lead,
)
from agents.builder import run_builder
from agents.checker import run_checker
from agents.diagnoser import run_diagnoser
from agents.filmer import run_filmer
from agents.mobile import run_mobile
from agents.pitcher import run_pitcher
from agents.scout import run_scout


@dataclass
class CycleResult:
    scouted: list[Lead] = field(default_factory=list)
    diagnosed: list[Lead] = field(default_factory=list)
    built: list[Lead] = field(default_factory=list)
    filmed: list[Lead] = field(default_factory=list)
    checked: list[Lead] = field(default_factory=list)
    pitched: list[Lead] = field(default_factory=list)
    mobile: list[Lead] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class Orchestrator:
    """Coordina el flujo multiagente con estado en filesystem."""

    def __init__(self) -> None:
        ensure_state_dirs()
        self.prompt = read_prompt("orchestrator")

    def log(self, message: str, level: str = "info", meta: Optional[dict] = None) -> None:
        log_event("Orchestrator", message, level=level, meta=meta)

    def escalate_high_value(self, leads: list[Lead]) -> list[Lead]:
        escalated = []
        for lead in leads:
            if lead.estimated_value_clp >= HIGH_VALUE_CLP and lead.status != LeadStatus.REVISION:
                lead.high_value = True
                lead.status = LeadStatus.REVISION
                lead.reason = (
                    (lead.reason or "")
                    + f" | deal {lead.estimated_value_clp:,} CLP → revision manual".replace(",", ".")
                )
                upsert_lead(lead)
                self.log(
                    f"deal {lead.estimated_value_clp:,} CLP → revision manual".replace(",", "."),
                    level="warn",
                    meta={"lead_id": lead.id},
                )
                escalated.append(lead)
        return escalated

    def run_demo(self, scout_count: int = 3, simulate_reply: bool = False) -> CycleResult:
        """
        Modo demo: Scout crea leads + pipeline avanza + flag high-value.
        High-value queda en revision; el resto avanza hasta enviado (simulado).
        """
        self.log("inicio ciclo DEMO")
        result = CycleResult()

        # 1) Scout
        result.scouted = run_scout(count=scout_count, force_high_value=True)

        # Separar high-value (HITL) del flujo automático de envío
        normal: list[Lead] = []
        high: list[Lead] = []
        for lead in result.scouted:
            if lead.estimated_value_clp >= HIGH_VALUE_CLP:
                high.append(lead)
            else:
                normal.append(lead)

        # High-value: diagnosticar + artefactos demo pero status revision (no envío)
        for lead in high:
            from agents.diagnoser import diagnose_lead
            from agents.builder import build_landing
            from agents.filmer import film_lead
            from agents.checker import check_lead

            lead = diagnose_lead(lead)  # marca REVISION
            result.diagnosed.append(lead)
            # Aun en revision generamos landing/storyboard para que el humano revise
            lead = build_landing(lead)
            result.built.append(lead)
            lead = film_lead(lead)
            result.filmed.append(lead)
            lead = check_lead(lead)
            result.checked.append(lead)
            self.log(
                f"HITL · {lead.business} listo para revisión humana (sin envío automático)",
                level="warn",
                meta={"lead_id": lead.id},
            )

        # Flujo normal completo
        if normal:
            result.diagnosed.extend(run_diagnoser(normal))
            # recargar desde disco por status
            diagnosed = [
                l for l in load_leads()
                if l.id in {x.id for x in normal} and l.status == LeadStatus.DIAGNOSTICADO
            ]
            result.built.extend(run_builder(diagnosed))
            landed = [
                l for l in load_leads()
                if l.id in {x.id for x in normal} and l.status == LeadStatus.LANDING
            ]
            result.filmed.extend(run_filmer(landed))
            videoed = [
                l for l in load_leads()
                if l.id in {x.id for x in normal} and l.status == LeadStatus.VIDEO
            ]
            result.checked.extend(run_checker(videoed))
            ready = [
                l for l in load_leads()
                if l.id in {x.id for x in normal} and l.status == LeadStatus.PITCH_LISTO
            ]
            result.pitched.extend(run_pitcher(ready))

            if simulate_reply:
                result.mobile = run_mobile(simulate_interest=True)

        result.counts = status_counts()
        self.log(
            "ciclo DEMO terminado · "
            + ", ".join(f"{k}={v}" for k, v in result.counts.items() if v > 0)
        )
        result.notes.append("Nunca se envía sin Checker. High-value → revision.")
        return result

    def run_cycle(self) -> CycleResult:
        """Un ciclo sobre estado existente + opcionalmente scoutea si no hay nuevos."""
        self.log("inicio ciclo")
        result = CycleResult()

        nuevos = [l for l in load_leads() if l.status == LeadStatus.NUEVO]
        if not nuevos:
            result.scouted = run_scout(count=2, force_high_value=False)
            nuevos = [l for l in load_leads() if l.status == LeadStatus.NUEVO]

        # Diagnóstico (incluye posible escalado HITL)
        result.diagnosed = run_diagnoser(nuevos)

        # Pipeline por status pendientes (no toca REVISION para envío)
        result.built = run_builder()
        result.filmed = run_filmer()
        result.checked = run_checker()
        result.pitched = run_pitcher()
        run_mobile(simulate_interest=False)

        result.counts = status_counts()
        self.log(
            "ciclo terminado · "
            + ", ".join(f"{k}={v}" for k, v in result.counts.items() if v > 0)
        )
        return result

    def run_scout_only(self, count: int = 3) -> list[Lead]:
        self.log(f"ejecutando solo Scout (n={count})")
        return run_scout(count=count, force_high_value=True)

    def snapshot(self) -> dict[str, Any]:
        leads = load_leads()
        return {
            "counts": status_counts(),
            "leads": leads,
            "total": len(leads),
        }


def run_demo() -> CycleResult:
    return Orchestrator().run_demo()


def run_cycle() -> CycleResult:
    return Orchestrator().run_cycle()
