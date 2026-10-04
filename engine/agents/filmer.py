"""Filmer: storyboard si no hay Chromium o FFmpeg. No lanza por binarios ausentes."""

from __future__ import annotations

from pathlib import Path

from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import log_event, output_dir, video_enabled
from agents.schemas import FilmerOutput
from core.config import get_settings
from core.states import transition
from db.models import Artifact, new_id
from db.repositories import ArtifactRepository, LeadRepository
from integrations.llm.base import build_llm
from integrations.video.base import Shot, Storyboard, build_video


class FilmerAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        if not ctx.lead_id:
            return AgentResult(lead_id=None, ok=False, events=["sin lead"], output={})
        lead = LeadRepository(ctx.session).get(ctx.lead_id)
        if lead is None:
            return AgentResult(
                lead_id=ctx.lead_id, ok=False, events=["lead inexistente"], output={}
            )
        if lead.status not in {"landing", "revision"}:
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})
        landing = _landing_path(ctx, lead.id)
        if landing is None:
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})
        if _storyboard(ctx, lead.id) is not None:
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})

        settings = get_settings()
        data = {
            "lead_id": lead.id,
            "business": lead.business,
            "commune": lead.commune,
            "category": lead.category,
        }
        script = build_llm(settings, ctx.session).complete_json("filmer", FilmerOutput, data)
        board = Storyboard(
            title=lead.business,
            duration_s=script.duration_s,
            voiceover=script.voiceover,
            shots=[Shot.model_validate(shot.model_dump()) for shot in script.shots],
        )

        def on_info(note: str) -> None:
            log_event("Filmer", note, level="info", session=ctx.session, lead_id=lead.id)

        result = build_video(settings, output_dir=output_dir(), on_info=on_info).render(
            Path(landing),
            board,
        )
        ArtifactRepository(ctx.session).add(
            Artifact(
                lead_id=lead.id,
                kind="video" if result.kind == "mp4" else "storyboard",
                path=result.path,
                public_token=new_id(),
                meta={"note": result.note},
            )
        )
        if lead.status == "landing":
            if video_enabled(ctx.session):
                transition(ctx.session, lead, "video", actor="agente", reason="storyboard listo")
                transition(
                    ctx.session,
                    lead,
                    "pitch_listo",
                    actor="agente",
                    reason="piezas listas para el pitch",
                )
            else:
                transition(
                    ctx.session,
                    lead,
                    "pitch_listo",
                    actor="agente",
                    reason="video deshabilitado",
                )
        message = f"storyboard · {lead.business}"
        log_event(
            "Filmer", message, session=ctx.session, lead_id=lead.id, meta={"path": result.path}
        )
        return AgentResult(
            lead_id=lead.id,
            ok=True,
            events=[message],
            output={"path": result.path, "kind": result.kind},
        )


def _landing_path(ctx: AgentContext, lead_id: str) -> str | None:
    rows = [
        item
        for item in ArtifactRepository(ctx.session).list(lead_id=lead_id, limit=20)
        if item.kind in {"landing_demo", "landing_prod"}
    ]
    return rows[-1].path if rows else None


def _storyboard(ctx: AgentContext, lead_id: str) -> Artifact | None:
    rows = [
        item
        for item in ArtifactRepository(ctx.session).list(lead_id=lead_id, limit=20)
        if item.kind in {"storyboard", "video"}
    ]
    return rows[-1] if rows else None
