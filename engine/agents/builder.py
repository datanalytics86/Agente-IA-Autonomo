"""Builder: Jinja2 con autoescape. En demo, noindex y sin datos inventados."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import update

from agents.catalog import THEME_BY_CATEGORY
from agents.context import AgentContext, AgentResult
from agents.copy import register_agent_fallbacks
from agents.runtime import ROOT, log_event, output_dir
from agents.schemas import LandingCopy
from core.config import get_settings
from core.states import transition
from db.models import Artifact, Lead, Project, new_id
from db.repositories import ArtifactRepository, LeadRepository, ProjectRepository
from integrations.hosting.base import project_slug, resolve_sites_dir
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
        if lead.status in {"en_produccion", "en_revision_cliente"}:
            return self._produce(ctx, lead)
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
                meta={"theme": theme, "demo": demo, "stage": "outreach"},
            )
        )
        if lead.status == "diagnosticado":
            transition(ctx.session, lead, "landing", actor="agente", reason="landing generada")
        message = f"landing HTML · {lead.business} → {path.name}"
        log_event(
            "Builder", message, session=ctx.session, lead_id=lead.id, meta={"path": str(path)}
        )
        return AgentResult(
            lead_id=lead.id, ok=True, events=[message], output={"path": str(path), "theme": theme}
        )

    def _produce(self, ctx: AgentContext, lead: Lead) -> AgentResult:
        projects = ProjectRepository(ctx.session).list(lead_id=lead.id, limit=5)
        if not projects:
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})
        project = projects[0]
        intake = project.intake if isinstance(project.intake, dict) else None
        if not intake:
            return AgentResult(lead_id=lead.id, ok=True, events=[], output={"skipped": True})
        existing = _production_artifact(ctx, lead.id)
        if existing is not None and Path(existing.path).is_file():
            _open_review(ctx, lead, project, existing.path)
            return AgentResult(
                lead_id=lead.id,
                ok=True,
                events=[],
                output={"path": existing.path, "skipped": True},
            )

        settings = get_settings()
        theme = THEME_BY_CATEGORY.get(lead.category, "servicios")
        copy = build_llm(settings, ctx.session).complete_json(
            "builder",
            LandingCopy,
            {
                "lead_id": lead.id,
                "business": lead.business,
                "category": lead.category,
                "commune": lead.commune,
                "city": lead.city,
                "theme": theme,
            },
        )
        items = _intake_items({str(key): value for key, value in intake.items()})
        html = _render_landing(
            lead_business=lead.business,
            commune=lead.commune,
            city=lead.city,
            category=lead.category,
            theme=theme,
            copy=copy,
            rating=lead.rating if isinstance(lead.rating, int | float) else None,
            reviews=lead.reviews if isinstance(lead.reviews, int) else None,
            booking_link=settings.booking_link,
            intake_items=items,
            preview=False,
        )
        token = new_id()
        filename = f"{_slug(lead.business)}-prod-{token[:8]}.html"
        path = output_dir() / filename
        path.write_text(html, encoding="utf-8")
        preview_html = _render_landing(
            lead_business=lead.business,
            commune=lead.commune,
            city=lead.city,
            category=lead.category,
            theme=theme,
            copy=copy,
            rating=lead.rating if isinstance(lead.rating, int | float) else None,
            reviews=lead.reviews if isinstance(lead.reviews, int) else None,
            booking_link=settings.booking_link,
            intake_items=items,
            preview=True,
        )
        slug = project_slug(project.portal_token)
        preview_path = resolve_sites_dir(settings) / "_previews" / slug
        preview_path.mkdir(parents=True, exist_ok=True)
        (preview_path / "index.html").write_text(preview_html, encoding="utf-8")
        ArtifactRepository(ctx.session).add(
            Artifact(
                lead_id=lead.id,
                project_id=project.id,
                kind="landing_prod",
                path=str(path),
                public_token=token,
                meta={"theme": theme, "demo": False, "stage": "production"},
            )
        )
        _open_review(ctx, lead, project, str(path))
        message = f"landing de producción · {lead.business} → {path.name}"
        log_event(
            "Builder", message, session=ctx.session, lead_id=lead.id, meta={"path": str(path)}
        )
        return AgentResult(
            lead_id=lead.id,
            ok=True,
            events=[message],
            output={"path": str(path), "theme": theme},
        )


_INTAKE_LABELS = {
    "objetivo": "Objetivo",
    "servicios": "Servicios",
    "horarios": "Horarios",
    "direccion": "Dirección",
    "telefono": "Teléfono",
    "descripcion": "Descripción",
}
_SKIP_INTAKE = frozenset({"feedback", "client_approved", "published_path", "balance_due_clp"})


def _intake_items(intake: dict[str, object]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key, value in intake.items():
        if key in _SKIP_INTAKE or key.startswith("_"):
            continue
        title = _INTAKE_LABELS.get(key, key)
        if isinstance(value, str) and value.strip():
            items.append({"title": title, "detail": value.strip()})
        elif isinstance(value, list):
            parts = [
                str(item).strip() for item in value if isinstance(item, str) and str(item).strip()
            ]
            if parts:
                items.append({"title": title, "detail": ", ".join(parts)})
    return items


def _production_artifact(ctx: AgentContext, lead_id: str) -> Artifact | None:
    rows = ArtifactRepository(ctx.session).list(lead_id=lead_id, limit=20)
    for item in rows:
        meta = item.meta if isinstance(item.meta, dict) else {}
        if item.kind == "landing_prod" and meta.get("stage") == "production":
            return item
    return None


def _render_landing(
    *,
    lead_business: str,
    commune: str,
    city: str,
    category: str,
    theme: str,
    copy: LandingCopy,
    rating: float | None,
    reviews: int | None,
    booking_link: str,
    intake_items: list[dict[str, str]],
    preview: bool,
) -> str:
    return (
        _env()
        .get_template(f"{theme}.html")
        .render(
            business=lead_business,
            commune=commune,
            city=city,
            category=category,
            theme=theme,
            hero_title=copy.hero_title,
            hero_subtitle=copy.hero_subtitle,
            services=copy.services,
            faqs=copy.faqs,
            about=copy.about,
            rating=rating,
            reviews=reviews,
            booking_link=booking_link,
            demo=False,
            preview=preview,
            token="",
            expires="",
            intake_items=intake_items,
        )
    )


def _open_review(ctx: AgentContext, lead: Lead, project: Project, production_path: str) -> None:
    current = dict(project.intake) if isinstance(project.intake, dict) else {}
    current["production_path"] = production_path
    if lead.status == "en_produccion":
        transition(
            ctx.session,
            lead,
            "en_revision_cliente",
            actor="agente",
            reason="landing de producción lista para el cliente",
        )
    if project.status in {"aprobado", "publicado"}:
        ctx.session.execute(update(Project).where(Project.id == project.id).values(intake=current))
        ctx.session.flush()
        return
    base = get_settings().public_base_url.rstrip("/") or "http://localhost"
    preview = f"{base}/api/public/proyecto/{project.portal_token}/preview"
    ctx.session.execute(
        update(Project)
        .where(Project.id == project.id)
        .values(status="en_revision_cliente", deploy_url=preview, intake=current)
    )
    ctx.session.flush()


def _existing(ctx: AgentContext, lead_id: str) -> Artifact | None:
    rows: list[Artifact] = []
    for item in ArtifactRepository(ctx.session).list(lead_id=lead_id, limit=20):
        if item.kind not in {"landing_demo", "landing_prod"}:
            continue
        meta = item.meta if isinstance(item.meta, dict) else {}
        if meta.get("stage") == "production":
            continue
        rows.append(item)
    return rows[-1] if rows else None


def render_theme(theme: str, **context: object) -> str:
    """Usado por tests para renderizar un tema sin pasar por el pipeline."""
    return _env().get_template(f"{theme}.html").render(**context)


def landing_path_for(path: Path) -> str:
    return str(path)
