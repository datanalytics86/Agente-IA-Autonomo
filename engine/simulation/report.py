"""Informe de la simulación y aserciones de §10."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.compliance import looks_like_injection
from core.config import ENGINE_DIR, get_settings
from core.hitl import needs_value_review
from db.models import (
    Approval,
    Artifact,
    Lead,
    LeadEvent,
    LlmCall,
    Message,
    Order,
    Payment,
    Project,
    Suppression,
)
from db.normalize import contact_hash
from db.repositories import SettingsRepository
from worker.schedule import in_send_window, is_business_day, local_date, to_local

FUNNEL = (
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
)
_PATH = (
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
)
_SENT = frozenset({"sent", "delivered", "bounced"})
_AUTO = frozenset({"instagram", "linkedin", "whatsapp"})


def write_report(
    session: Session,
    *,
    path: Path,
    seed: int,
    days: int,
    started: datetime,
    finished: datetime,
    network_calls: int,
) -> int:
    violations = collect_violations(
        session,
        started=started,
        network_calls=network_calls,
    )
    text = render(
        session,
        seed=seed,
        days=days,
        started=started,
        finished=finished,
        network_calls=network_calls,
        violations=violations,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return 0 if not violations else 1


def collect_violations(
    session: Session,
    *,
    started: datetime,
    network_calls: int,
) -> list[str]:
    leads = list(session.scalars(select(Lead).order_by(Lead.business.asc(), Lead.id.asc())).all())
    messages = list(session.scalars(select(Message)).all())
    by_lead: dict[str, list[Message]] = defaultdict(list)
    for message in messages:
        by_lead[message.lead_id].append(message)
    lead_by_id = {lead.id: lead for lead in leads}
    found: list[str] = []
    found.extend(_checker(messages, lead_by_id))
    found.extend(_suppression(session, messages, leads))
    found.extend(_window(messages))
    found.extend(_manual(messages))
    found.extend(_quotas(session, messages, lead_by_id, local_date(started)))
    found.extend(_sequences(messages, leads, by_lead))
    if network_calls:
        found.append(f"llamadas de red: {network_calls}")
    found.extend(_injection(messages, lead_by_id, by_lead))
    found.extend(_high_value(leads, by_lead))
    found.extend(_response_rate(session))
    found.extend(_delivered(session, leads))
    found.extend(_round2(session, messages))
    return found


def render(
    session: Session,
    *,
    seed: int,
    days: int,
    started: datetime,
    finished: datetime,
    network_calls: int,
    violations: list[str],
) -> str:
    leads = list(session.scalars(select(Lead)).all())
    messages = list(session.scalars(select(Message)).all())
    approvals = list(session.scalars(select(Approval)).all())
    counts = {status: 0 for status in FUNNEL}
    for lead in leads:
        if lead.source == "sistema":
            continue
        counts[lead.status] = counts.get(lead.status, 0) + 1
    msg_counts: dict[str, int] = defaultdict(int)
    for message in messages:
        msg_counts[message.status] += 1
    revenue = sum(int(row.amount_clp) for row in session.scalars(select(Payment)).all())
    paused = SettingsRepository(session).get("channel_paused")
    paused_label = "ninguno"
    if isinstance(paused, dict):
        names = sorted(key for key, value in paused.items() if value is True)
        if names:
            paused_label = ", ".join(names)
    kinds: dict[str, int] = defaultdict(int)
    for row in approvals:
        kinds[row.kind] += 1
    kind_text = ", ".join(f"{name}={kinds[name]}" for name in sorted(kinds)) or "ninguno"
    lines = [
        f"# Simulación seed {seed} · {days} días",
        "",
        f"Inicio: {_iso(started)}",
        f"Fin: {_iso(finished)}",
        "",
        "## Embudo",
        "",
        "| Estado | Leads |",
        "| --- | --- |",
    ]
    for status in FUNNEL:
        lines.append(f"| {status} | {counts.get(status, 0)} |")
    lines.extend(["", "## Mensajes", "", "| Status | Cantidad |", "| --- | --- |"])
    for status in sorted(msg_counts):
        lines.append(f"| {status} | {msg_counts[status]} |")
    lines.extend(
        [
            "",
            "## Métricas",
            "",
            f"- enviados: {msg_counts.get('sent', 0)}",
            f"- rebotes: {msg_counts.get('bounced', 0)}",
            f"- ingresos_clp: {revenue}",
            f"- canal_pausado: {paused_label}",
            f"- approvals: {kind_text}",
            f"- llamadas_de_red: {network_calls}",
            "",
            "## Aserciones",
            "",
        ]
    )
    if violations:
        lines.extend(f"- {item}" for item in violations)
    else:
        lines.append("- todas las aserciones de la sección 10 pasan")
    lines.extend(["", f"violaciones: {len(violations)}", ""])
    return "\n".join(lines)


def _iso(moment: datetime) -> str:
    return to_local(moment).isoformat(timespec="seconds")


def _checker(messages: list[Message], leads: dict[str, Lead]) -> list[str]:
    found: list[str] = []
    for message in messages:
        if message.channel != "email_outreach" or message.status not in _SENT:
            continue
        result = message.check_result if isinstance(message.check_result, dict) else {}
        if result.get("approved") is True:
            continue
        business = leads[message.lead_id].business if message.lead_id in leads else message.lead_id
        found.append(f"envío sin checker: {business}")
    return found


def _suppression(session: Session, messages: list[Message], leads: list[Lead]) -> list[str]:
    found: list[str] = []
    rows = list(session.scalars(select(Suppression)).all())
    by_hash = {(row.kind, row.value_hash): row for row in rows}
    for lead in leads:
        if not lead.contact_email:
            continue
        digest = contact_hash("email", lead.contact_email)
        row = by_hash.get(("email", digest))
        if row is None:
            continue
        for message in messages:
            if message.lead_id != lead.id or message.status not in _SENT:
                continue
            if message.sent_at is None or message.sent_at < row.created_at:
                continue
            found.append(f"envío tras opt-out: {lead.business}")
    return found


def _window(messages: list[Message]) -> list[str]:
    found: list[str] = []
    for message in messages:
        if message.channel != "email_outreach" or message.status not in _SENT:
            continue
        if message.sent_at is None or not in_send_window(message.sent_at):
            found.append("envío fuera de ventana o feriado")
    return found


def _manual(messages: list[Message]) -> list[str]:
    found: list[str] = []
    for message in messages:
        if message.channel in _AUTO and message.status in {"sent", "delivered"}:
            found.append(f"envío automático {message.channel}")
    return found


def _quotas(
    session: Session,
    messages: list[Message],
    leads: dict[str, Lead],
    start_day: date,
) -> list[str]:
    per_day: dict[date, int] = defaultdict(int)
    per_domain: dict[tuple[date, str], int] = defaultdict(int)
    for message in messages:
        if message.channel != "email_outreach" or message.status not in _SENT:
            continue
        if message.sent_at is None:
            continue
        day = local_date(message.sent_at)
        per_day[day] += 1
        lead = leads.get(message.lead_id)
        email = lead.contact_email if lead and lead.contact_email else ""
        domain = email.split("@", 1)[1].lower() if "@" in email else ""
        per_domain[(day, domain)] += 1
    found: list[str] = []
    for day, count in sorted(per_day.items()):
        if count > _limit_on(day, start_day):
            found.append(f"cupo diario excedido {day.isoformat()}: {count}")
    for (day, domain), count in sorted(per_domain.items()):
        if domain and count > 1:
            found.append(f"cupo por dominio excedido {domain} {day.isoformat()}")
    return found


def _limit_on(day: date, start_day: date) -> int:
    settings = get_settings()
    limit = settings.email_outreach_daily_limit
    cursor = start_day
    while cursor <= day:
        if cursor.weekday() == 0 and is_business_day(cursor):
            limit = min(settings.email_outreach_daily_max, limit + 5)
        cursor += timedelta(days=1)
    return limit


def _sequences(
    messages: list[Message],
    leads: list[Lead],
    by_lead: dict[str, list[Message]],
) -> list[str]:
    found: list[str] = []
    for lead in leads:
        rows = by_lead.get(lead.id, [])
        stops: list[datetime] = []
        for message in rows:
            if message.direction == "in" and message.created_at is not None:
                stops.append(_aware(message.created_at))
            if message.status == "bounced" and message.sent_at is not None:
                stops.append(_aware(message.sent_at))
        if not stops:
            continue
        stop = min(stops)
        for message in rows:
            step = message.sequence_step or 0
            if message.direction != "out" or step <= 1 or message.status not in _SENT:
                continue
            if message.sent_at is not None and _aware(message.sent_at) >= stop:
                found.append(f"secuencia continúa: {lead.business} paso {step}")
    return found


def _injection(
    messages: list[Message],
    leads: dict[str, Lead],
    by_lead: dict[str, list[Message]],
) -> list[str]:
    found: list[str] = []
    for lead in leads.values():
        if lead.contact_email and "evil.test" in lead.contact_email:
            found.append("contacto creado desde una inyección")
    forbidden = {"pagado", "propuesta", "agendado", "entregado", "en_produccion"}
    for message in messages:
        if message.direction != "in":
            continue
        if not looks_like_injection(message.body_text or ""):
            continue
        owner = leads.get(message.lead_id)
        if owner is None:
            continue
        if owner.status in forbidden:
            found.append(f"acción derivada de inyección: {owner.business}")
        for other in by_lead.get(owner.id, []):
            step = other.sequence_step or 0
            if other.direction == "out" and step > 1 and other.status in _SENT:
                found.append(f"envío derivado de inyección: {owner.business}")
    return found


def _high_value(leads: list[Lead], by_lead: dict[str, list[Message]]) -> list[str]:
    highs = [
        lead
        for lead in leads
        if lead.source != "sistema"
        and (lead.high_value or needs_value_review(lead.estimated_value_clp))
    ]
    found: list[str] = []
    if not highs or not any(lead.status == "revision" for lead in highs):
        found.append("el lead de alto valor no terminó en revision")
    for lead in highs:
        for message in by_lead.get(lead.id, []):
            if message.status in _SENT:
                found.append(f"alto valor recibió envío: {lead.business}")
    return found


def _response_rate(session: Session) -> list[str]:
    paused = SettingsRepository(session).get("channel_paused")
    armed = isinstance(paused, dict) and paused.get("email_outreach") is True
    rows = select(Approval).where(Approval.kind == "tasa_respuesta_baja")
    approvals = list(session.scalars(rows).all())
    if armed and approvals:
        return []
    return ["la tasa baja no pausó el canal o no creó el approval"]


def _delivered(session: Session, leads: list[Lead]) -> list[str]:
    found: list[str] = []
    events = list(session.scalars(select(LeadEvent)).all())
    by_lead: dict[str, set[str]] = defaultdict(set)
    for event in events:
        by_lead[event.lead_id].add(event.to_status)
    walked = any(all(step in seen for step in _PATH) for seen in by_lead.values())
    if not walked:
        found.append("ningún lead recorrió el embudo hasta entregado")
    revenue = sum(int(row.amount_clp) for row in session.scalars(select(Payment)).all())
    if revenue <= 0:
        found.append("no hay pago registrado")
    metrics = SettingsRepository(session).get("metrics_latest")
    reported = 0
    if isinstance(metrics, dict):
        try:
            reported = int(metrics.get("revenue_clp") or 0)
        except (TypeError, ValueError):
            reported = -1
    if reported != revenue or reported <= 0:
        found.append("los ingresos no están reflejados en las métricas")
    if not any(lead.status in {"entregado", "postventa"} for lead in leads):
        found.append("ningún lead está entregado")
    return found


def _round2(session: Session, messages: list[Message]) -> list[str]:
    """Aserciones de la §7.3. El informe las suma a las de la ronda 1."""
    found: list[str] = []
    found.extend(_artifacts_on_disk(session))
    found.extend(_llm_is_fake(session))
    found.extend(_publication_gates(session))
    found.extend(_mobile_classified(messages))
    found.extend(_bounces_suppressed(session, messages))
    if not _informe_sent(messages):
        found.append("no se envió el informe de diagnóstico gratis")
    return found


def _artifact_file(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    return ENGINE_DIR / candidate


def _artifacts_on_disk(session: Session) -> list[str]:
    found: list[str] = []
    for row in session.scalars(select(Artifact)).all():
        if not _artifact_file(row.path).is_file():
            found.append(f"artefacto sin archivo: {row.kind}")
    return found


def _llm_is_fake(session: Session) -> list[str]:
    found: list[str] = []
    for row in session.scalars(select(LlmCall)).all():
        if row.model != "deterministic-fallback":
            found.append(f"llm_call fuera de FakeLlm: {row.model}")
        if row.tokens_in == 120 and row.cost_usd == Decimal("0.001"):
            found.append("llm_call con la fila falsa de tokens")
    return found


def _publication_gates(session: Session) -> list[str]:
    found: list[str] = []
    projects = list(session.scalars(select(Project).where(Project.status == "publicado")).all())
    if not projects:
        found.append("no hay publicación con saldo pagado")
    for project in projects:
        intake = project.intake if isinstance(project.intake, dict) else {}
        if intake.get("client_approved") is not True:
            found.append("entrega sin aprobación del cliente")
        order = session.get(Order, project.order_id)
        if order is None or order.status != "paid":
            found.append("publicación sin saldo pagado")
            continue
        paid = sum(
            int(row.amount_clp)
            for row in session.scalars(select(Payment).where(Payment.order_id == order.id)).all()
            if row.status == "approved"
        )
        if paid < order.total_clp:
            found.append("publicación sin saldo pagado")
    return found


def _mobile_classified(messages: list[Message]) -> list[str]:
    pending = [
        message
        for message in messages
        if message.direction == "in"
        and message.channel == "email_outreach"
        and message.intent is None
    ]
    if pending:
        return ["respuesta IMAP sin intención no clasificada por Mobile"]
    classified = [
        message
        for message in messages
        if message.direction == "in"
        and message.channel == "email_outreach"
        and message.intent_confidence is not None
    ]
    if not classified:
        return ["ninguna respuesta sin intención pasó por Mobile"]
    return []


def _bounces_suppressed(session: Session, messages: list[Message]) -> list[str]:
    bounced = [message for message in messages if message.status == "bounced"]
    if not bounced:
        return ["ningún rebote quedó en supresión"]
    rows = list(session.scalars(select(Suppression).where(Suppression.kind == "email")).all())
    hashes = {row.value_hash for row in rows}
    found: list[str] = []
    leads = {lead.id: lead for lead in session.scalars(select(Lead)).all()}
    for message in bounced:
        lead = leads.get(message.lead_id)
        email = lead.contact_email if lead is not None else ""
        if not email or contact_hash("email", email) not in hashes:
            found.append("rebote sin supresión")
    return found


def _informe_sent(messages: list[Message]) -> bool:
    for message in messages:
        meta = message.check_result if isinstance(message.check_result, dict) else {}
        if (
            message.channel == "email_tx"
            and message.direction == "out"
            and message.status == "sent"
            and meta.get("kind") == "informe_diagnostico"
        ):
            return True
    return False


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)
