"""Builder: Jinja2 con autoescape. En demo, noindex y sin datos inventados."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agents.catalog import THEME_BY_CATEGORY
from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import ROOT, log_event, output_dir
from agents.schemas import LandingCopy
from core.config import get_settings
from db.models import Artifact, new_id
from db.repositories import ArtifactRepository, LeadRepository
from integrations.llm.base import build_llm

_TEMPLATES = ROOT / "templates" / "landings"
_ENV: Environment | None = None


def _env() -> Environment:
    global _ENV
    if _ENV is None:
        _ENV = Environment(
            loader=FileSystemLoader(_TEMPLATES),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _ENV


def _slug(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = plain.lower().replace("ñ", "n")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")[:48] or "landing"


class BuilderAgent:
    def run(self, ctx: AgentContext) -> AgentResult:
        register_agent_fallbacks()
        if not ctx.lead_id:
            return AgentResult(lead_id=None, ok=False, events=["sin lead"], output={})
        lead = LeadRepository(ctx.session).get(ctx.lead_id)
        if lead is None:
            return AgentResult(
                lead_id=ctx.lead_id, ok=False, events=["lead inexistente"], output={}
            )
        if lead.status not in {"diagnosticado", "revision"}:
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})
        existing = _existing(ctx, lead.id)
        if existing is not None:
            return AgentResult(
                lead_id=lead.id,
                ok=True,
                events=[],
                output={"path": existing.path, "skipped": True},
            )

        settings = get_settings()
        theme = THEME_BY_CATEGORY.get(lead.category, "servicios")
        data = {
            "lead_id": lead.id,
            "business": lead.business,
            "category": lead.category,
            "commune": lead.commune,
            "city": lead.city,
            "theme": theme,
        }
        copy = build_llm(settings, ctx.session).complete_json("builder", LandingCopy, data)
        token = new_id()
        demo = settings.app_mode == "demo"
        expires = datetime.now(UTC) + timedelta(days=settings.demo_ttl_days)
        html = (
            _env()
            .get_template(f"{theme}.html")
            .render(
                business=lead.business,
                commune=lead.commune,
                city=lead.city,
                category=lead.category,
                theme=theme,
                hero_title=copy.hero_title,
                hero_subtitle=copy.hero_subtitle,
                services=copy.services,
                faqs=copy.faqs,
                about=copy.about,
                rating=lead.rating,
                reviews=lead.reviews,
                booking_link=settings.booking_link,
                demo=demo,
                token=token,
                expires=expires.date().isoformat(),
            )
        )
        filename = f"{_slug(lead.business)}-{token[:8]}.html"
        path = output_dir() / filename
        path.write_text(html, encoding="utf-8")
        ArtifactRepository(ctx.session).add(
            Artifact(
                lead_id=lead.id,
                kind="landing_demo" if demo else "landing_prod",
                path=str(path),
                public_token=token,
                expires_at=expires if demo else None,
                meta={"theme": theme, "demo": demo},
            )
        )
        from core.states import transition

        if lead.status == "diagnosticado":
            transition(ctx.session, lead, "landing", actor="agente", reason="landing generada")
        message = f"landing HTML · {lead.business} → {path.name}"
        log_event(
            "Builder", message, session=ctx.session, lead_id=lead.id, meta={"path": str(path)}
        )
        return AgentResult(
            lead_id=lead.id, ok=True, events=[message], output={"path": str(path), "theme": theme}
        )


def _existing(ctx: AgentContext, lead_id: str) -> Artifact | None:
    rows = [
        item
        for item in ArtifactRepository(ctx.session).list(lead_id=lead_id, limit=20)
        if item.kind in {"landing_demo", "landing_prod"}
    ]
    return rows[-1] if rows else None


def render_theme(theme: str, **context: object) -> str:
    """Usado por tests para renderizar un tema sin pasar por el pipeline."""
    return _env().get_template(f"{theme}.html").render(**context)


def landing_path_for(path: Path) -> str:
    return str(path)
