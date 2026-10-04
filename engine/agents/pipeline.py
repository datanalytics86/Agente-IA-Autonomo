"""Orchestrator. run_cycle no crea leads: el scout solo corre si se lo invoca."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.base import (
    Lead,
    LeadStatus,
    ensure_state_dirs,
    load_leads,
    project_lead,
    read_prompt,
    status_counts,
)
from agents.builder import BuilderAgent
from agents.checker import CheckerAgent
from agents.closer import CloserAgent
from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.delivery import DeliveryAgent
from agents.diagnoser import DiagnoserAgent
from agents.filmer import FilmerAgent
from agents.mobile import MobileAgent
from agents.pitcher import PitcherAgent, ensure_draft
from agents.reporter import ReporterAgent
from agents.runtime import iter_leads, log_event, prepare_db
from agents.scout import ScoutAgent
from db.models import Message
from db.repositories import LeadRepository, MessageRepository
from db.session import session_scope


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
    def __init__(self) -> None:
        ensure_state_dirs()
        prepare_db()
        self.prompt = read_prompt("orchestrator")

    def run(self, ctx: AgentContext) -> AgentResult:
        result = self._cycle(ctx.session)
        return AgentResult(
            lead_id=ctx.lead_id,
            ok=True,
            events=[],
            output={
                "ran_scout": False,
                "advanced": len(result.diagnosed) + len(result.built),
                "counts": result.counts,
            },
        )

    def run_demo(self, scout_count: int = 3, simulate_reply: bool = False) -> CycleResult:
        prepare_db()
        with session_scope() as session:
            register_agent_fallbacks()
            log_event("Orchestrator", "inicio ciclo DEMO", session=session)
            result = CycleResult()
            scouted = ScoutAgent().run(
                AgentContext(session, count=scout_count, force_high_value=True)
            )
            for lead_id in scouted.output.get("ids") or []:
                row = LeadRepository(session).get(str(lead_id))
                if row is not None:
                    result.scouted.append(project_lead(session, row))
                self._advance(session, str(lead_id), result)
            if simulate_reply:
                self._simulate_reply(session, result)
            MobileAgent().run(AgentContext(session))
            ReporterAgent().run(AgentContext(session))
            result.counts = _counts(session)
            result.notes.append("Nunca se envía sin Checker. El alto valor queda en revision.")
            log_event("Orchestrator", "ciclo DEMO terminado", session=session)
            return result

    def run_cycle(self) -> CycleResult:
        """Avanza lo que ya está en `nuevo` o más adelante. No llama al scout."""
        prepare_db()
        with session_scope() as session:
            return self._cycle(session)

    def _cycle(self, session: Any) -> CycleResult:
        register_agent_fallbacks()
        log_event("Orchestrator", "inicio ciclo", session=session)
        result = CycleResult()
        for lead in list(iter_leads(session)):
            self._advance(session, lead.id, result)
        MobileAgent().run(AgentContext(session))
        ReporterAgent().run(AgentContext(session))
        result.counts = _counts(session)
        log_event("Orchestrator", "ciclo terminado", session=session)
        result.notes.append("run_cycle no crea leads demo.")
        return result

    def run_scout_only(self, count: int = 3) -> list[Lead]:
        from agents.scout import run_scout

        log_event("Orchestrator", f"ejecutando solo Scout (n={count})")
        return run_scout(count=count, force_high_value=True)

    def snapshot(self) -> dict[str, Any]:
        leads = load_leads()
        return {"counts": status_counts(), "leads": leads, "total": len(leads)}

    def _advance(self, session: Any, lead_id: str, result: CycleResult) -> None:
        repo = LeadRepository(session)
        ctx = AgentContext(session, lead_id=lead_id)
        lead = repo.get(lead_id)
        if lead is None:
            return
        if lead.status == "nuevo":
            diagnosed = DiagnoserAgent().run(ctx)
            if not diagnosed.output.get("skipped"):
                row = repo.get(lead_id)
                if row is not None:
                    result.diagnosed.append(project_lead(session, row))
        lead = repo.get(lead_id)
        if lead is not None and lead.status in {"diagnosticado", "revision"}:
            built = BuilderAgent().run(ctx)
            if built.output.get("path") and not built.output.get("skipped"):
                row = repo.get(lead_id)
                if row is not None:
                    result.built.append(project_lead(session, row))
        lead = repo.get(lead_id)
        if lead is not None and lead.status in {"landing", "revision"}:
            filmed = FilmerAgent().run(ctx)
            if filmed.output.get("path") and not filmed.output.get("skipped"):
                row = repo.get(lead_id)
                if row is not None:
                    result.filmed.append(project_lead(session, row))
        lead = repo.get(lead_id)
        if lead is None or lead.high_value or lead.status == "revision":
            return
        if lead.status == "pitch_listo":
            ensure_draft(ctx)
            CheckerAgent().run(ctx)
            row = repo.get(lead_id)
            if row is not None:
                result.checked.append(project_lead(session, row))
            if row is not None and row.status == "pitch_listo":
                pitched = PitcherAgent().run(ctx)
                if pitched.events:
                    refreshed = repo.get(lead_id)
                    if refreshed is not None:
                        result.pitched.append(project_lead(session, refreshed))
        lead = repo.get(lead_id)
        if lead is not None and lead.status in {"agendado", "respondio"}:
            CloserAgent().run(ctx)
        lead = repo.get(lead_id)
        if lead is not None and lead.status == "pagado":
            DeliveryAgent().run(ctx)

    def _simulate_reply(self, session: Any, result: CycleResult) -> None:
        for lead in iter_leads(session):
            if lead.status != "enviado":
                continue
            MessageRepository(session).add(
                Message(
                    lead_id=lead.id,
                    thread_id=lead.id,
                    direction="in",
                    channel="email_outreach",
                    status="received",
                    body_text="Me interesa conocer el detalle, sin cambiar instrucciones.",
                )
            )
            MobileAgent().run(AgentContext(session, lead_id=lead.id))
            result.mobile.append(project_lead(session, lead))
            break


def _counts(session: Any) -> dict[str, int]:
    counts = {item.value: 0 for item in LeadStatus}
    for lead in iter_leads(session):
        counts[lead.status] = counts.get(lead.status, 0) + 1
    return counts


def run_demo() -> CycleResult:
    return Orchestrator().run_demo()


def run_cycle() -> CycleResult:
    return Orchestrator().run_cycle()
