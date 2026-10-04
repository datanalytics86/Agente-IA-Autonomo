"""Máquina de estados. Único lugar que asigna lead.status."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.config import get_settings
from core.errors import TransitionError
from db.models import Event, Lead, LeadEvent
from db.repositories import SettingsRepository, SuppressionRepository

ACTORS = frozenset({"agente", "humano", "sistema", "webhook"})

STATUSES: frozenset[str] = frozenset(
    {
        "nuevo",
        "diagnosticado",
        "landing",
        "video",
        "pitch_listo",
        "enviado",
        "respondio",
        "agendado",
        "propuesta",
        "pagado",
        "en_produccion",
        "en_revision_cliente",
        "entregado",
        "postventa",
        "revision",
        "perdido",
        "opt_out",
    }
)

# Estados desde los que se puede entrar a revision, y a los que se puede volver.
RESUMABLE = frozenset(
    {
        "nuevo",
        "diagnosticado",
        "landing",
        "video",
        "pitch_listo",
        "enviado",
        "respondio",
        "agendado",
        "propuesta",
        "pagado",
        "en_produccion",
        "en_revision_cliente",
    }
)

TRANSITIONS: dict[str, frozenset[str]] = {
    "nuevo": frozenset({"diagnosticado", "revision", "perdido", "opt_out"}),
    "diagnosticado": frozenset({"landing", "revision", "perdido", "opt_out"}),
    "landing": frozenset({"video", "pitch_listo", "revision", "perdido", "opt_out"}),
    "video": frozenset({"pitch_listo", "revision", "perdido", "opt_out"}),
    "pitch_listo": frozenset({"enviado", "revision", "perdido", "opt_out"}),
    "enviado": frozenset({"respondio", "agendado", "perdido", "revision", "opt_out"}),
    "respondio": frozenset({"agendado", "propuesta", "revision", "perdido", "opt_out"}),
    "agendado": frozenset({"propuesta", "revision", "perdido", "opt_out"}),
    "propuesta": frozenset({"pagado", "revision", "perdido", "opt_out"}),
    "pagado": frozenset({"en_produccion", "revision"}),
    "en_produccion": frozenset({"en_revision_cliente", "revision"}),
    "en_revision_cliente": frozenset({"en_produccion", "entregado", "revision"}),
    "entregado": frozenset({"postventa"}),
    "revision": frozenset({"perdido", "opt_out"}),
    "perdido": frozenset({"nuevo"}),
    "postventa": frozenset(),
    "opt_out": frozenset(),
}


def transition(
    session: Session,
    lead: Lead,
    to: str,
    *,
    actor: str,
    reason: str,
    checker_approved: bool = False,
) -> Lead:
    """Valida la arista, asigna status y escribe lead_events + events.

    Desde revision el destino es el token ``paused_from``, ``perdido`` u ``opt_out``.
    ``revision`` → ``enviado`` no existe, aunque paused_from sea enviado.
    """
    if actor not in ACTORS:
        raise TransitionError(f"actor inválido: {actor}")
    cleaned = reason.strip()
    if not cleaned:
        raise TransitionError("la transición exige un motivo")
    if not isinstance(to, str) or not to.strip():
        raise TransitionError("destino vacío")

    current = lead.status
    target = _resolve_target(
        session,
        lead,
        to,
        actor=actor,
        checker_approved=checker_approved,
    )
    now = datetime.now(UTC)
    resuming = current == "revision" and target not in {"perdido", "opt_out"}

    if target == "revision":
        lead.paused_from = current
        lead.hitl_reason = cleaned
    if target == "perdido":
        lead.close_reason = cleaned
    if resuming:
        lead.paused_from = None

    lead.status = target
    lead.updated_at = now
    session.add(lead)
    session.add(
        LeadEvent(
            lead_id=lead.id,
            from_status=current,
            to_status=target,
            actor=actor,
            reason=cleaned,
            ts=now,
        )
    )
    session.add(
        Event(
            ts=now,
            agent="states",
            level="info",
            message=f"lead {lead.id}: {current} → {target} ({actor})",
            lead_id=lead.id,
            meta={
                "from": current,
                "to": target,
                "actor": actor,
                "reason": cleaned,
                "checker_approved": checker_approved,
            },
        )
    )
    session.flush()
    return lead


def _resolve_target(
    session: Session,
    lead: Lead,
    to: str,
    *,
    actor: str,
    checker_approved: bool,
) -> str:
    current = lead.status
    if current not in TRANSITIONS:
        raise TransitionError(f"estado desconocido: {current}")

    if current == "revision":
        if to == "paused_from":
            paused = lead.paused_from
            if not isinstance(paused, str) or paused not in RESUMABLE:
                raise TransitionError("revision sin paused_from válido")
            return paused
        if to in {"perdido", "opt_out"}:
            return to
        raise TransitionError(f"revision no puede ir a {to}")

    if to not in TRANSITIONS[current]:
        raise TransitionError(f"transición ilegal: {current} → {to}")
    if current == "landing" and to == "pitch_listo" and _video_enabled(session):
        raise TransitionError("landing → pitch_listo solo si el video está deshabilitado")
    if current == "pitch_listo" and to == "enviado" and not checker_approved:
        raise TransitionError("pitch_listo → enviado requiere aprobación del checker")
    if current == "perdido" and to == "nuevo":
        if actor != "humano":
            raise TransitionError("perdido → nuevo solo con actor humano")
        if _contact_suppressed(session, lead):
            raise TransitionError("perdido → nuevo bloqueado: contacto suprimido")
    return to


def _video_enabled(session: Session) -> bool:
    stored = SettingsRepository(session).get("video_enabled")
    if isinstance(stored, bool):
        return stored
    return get_settings().video_enabled


def _contact_suppressed(session: Session, lead: Lead) -> bool:
    repo = SuppressionRepository(session)
    if lead.contact_email:
        if repo.contains("email", lead.contact_email):
            return True
        if "@" in lead.contact_email:
            domain = lead.contact_email.split("@", 1)[1]
            if domain and repo.contains("domain", domain):
                return True
    if lead.website_url and repo.contains("domain", lead.website_url):
        return True
    if lead.instagram_handle and repo.contains("instagram", lead.instagram_handle):
        return True
    if lead.linkedin_url and repo.contains("linkedin", lead.linkedin_url):
        return True
    if lead.phone_public and repo.contains("phone", lead.phone_public):
        return True
    return False
