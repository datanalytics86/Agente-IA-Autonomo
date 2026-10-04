"""Casos de uso de la API. El status de un lead solo cambia con transition()."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.catalog import (
    CATEGORIES,
    CATEGORY_SLUGS,
    HIGH_VALUE_CATEGORIES,
    PACKAGES,
    revisions_for,
    split_iva,
    tone_for,
)
from api.deps import PaymentFact, PaymentProvider
from api.errors import ApiError, error_body
from api.present import (
    artifact_dict,
    event_dict,
    lead_dict,
    message_dict,
    order_dict,
    project_dict,
    timeline_dict,
)
from api.schemas import LeadPatch, SettingsIn
from api.security import consent_record, read_baja_token, text_version
from core.config import ENGINE_DIR, get_settings
from core.states import STATUSES, TRANSITIONS
from core.states import transition as transition_lead
from db.models import (
    Approval,
    Artifact,
    DataRequest,
    Event,
    Lead,
    LeadEvent,
    LlmCall,
    Message,
    Order,
    Payment,
    Project,
    Suppression,
    WebhookEvent,
    utcnow,
)
from db.normalize import CONTACT_KINDS, normalize_contact
from db.repositories import (
    ApprovalRepository,
    DataRequestRepository,
    EventRepository,
    JobRunRepository,
    LeadRepository,
    MessageRepository,
    OrderRepository,
    ProjectRepository,
    SettingsRepository,
    SuppressionRepository,
    _start_of_local_day,
)

_RIGHTS = frozenset(
    {"acceso", "rectificacion", "supresion", "oposicion", "portabilidad", "bloqueo"}
)
_PROJECT_STATUSES = frozenset(
    {"intake_pendiente", "en_produccion", "en_revision_cliente", "aprobado", "publicado"}
)
_PAID = frozenset({"approved", "paid"})
_SENT = frozenset({"sent", "manual_sent", "delivered"})


def _packages_view(session: Session) -> list[dict[str, Any]]:
    stored = SettingsRepository(session).get("prices")
    overrides = stored if isinstance(stored, dict) else {}
    rows: list[dict[str, Any]] = []
    for item in PACKAGES:
        price = item["price_clp"]
        if item["code"] in overrides:
            raw = overrides[item["code"]]
            if isinstance(raw, dict):
                raw = raw.get("price_clp", price)
            price = None if raw is None else int(raw)
        rows.append(
            {
                "code": item["code"],
                "name": item["name"],
                "price_clp": price,
                "revisions": item["revisions"],
                "includes": list(item["includes"]),
            }
        )
    return rows


def _price_of(session: Session, code: str) -> int | None:
    for item in _packages_view(session):
        if item["code"] == code:
            value = item["price_clp"]
            return None if value is None else int(value)
    raise ApiError(422, "validation_error", "paquete desconocido")


def default_quotas() -> dict[str, int]:
    settings = get_settings()
    return {
        "scout_daily_limit": settings.scout_daily_limit,
        "diagnose_daily_limit": settings.diagnose_daily_limit,
        "email_outreach_daily_limit": settings.email_outreach_daily_limit,
        "email_outreach_daily_max": settings.email_outreach_daily_max,
    }


def default_prices() -> dict[str, int | None]:
    return {str(item["code"]): item["price_clp"] for item in PACKAGES}


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    return default


def read_settings_view(session: Session) -> dict[str, Any]:
    repo = SettingsRepository(session)
    quotas = repo.get("quotas")
    prices = repo.get("prices")
    rates = repo.get("hitl_response_rate_by_channel")
    clean_rates: dict[str, float] = {}
    if isinstance(rates, dict):
        for key, raw in rates.items():
            try:
                clean_rates[str(key)] = float(raw)
            except (TypeError, ValueError):
                continue
    return {
        "kill_switch": _as_bool(repo.get("kill_switch", False)),
        "app_mode": get_settings().app_mode,
        "quotas": quotas if isinstance(quotas, dict) else default_quotas(),
        "prices": prices if isinstance(prices, dict) else default_prices(),
        "hitl_response_rate_by_channel": clean_rates,
    }


def write_settings(session: Session, email: str, payload: SettingsIn) -> dict[str, Any]:
    repo = SettingsRepository(session)
    repo.put("kill_switch", payload.kill_switch, updated_by=email)
    if payload.quotas is not None:
        repo.put("quotas", payload.quotas, updated_by=email)
    if payload.prices is not None:
        repo.put("prices", payload.prices, updated_by=email)
    if payload.hitl_response_rate_by_channel is not None:
        repo.put(
            "hitl_response_rate_by_channel",
            payload.hitl_response_rate_by_channel,
            updated_by=email,
        )
    return read_settings_view(session)


def submit_diagnostico(
    session: Session,
    *,
    business: str,
    email: str,
    commune: str,
    category: str,
    consent_text: str,
    website_url: str | None,
    ip: str,
) -> dict[str, str]:
    if category not in CATEGORY_SLUGS:
        raise ApiError(422, "validation_error", "rubro desconocido")
    price = _price_of(session, "landing_esencial") or 0
    lead = Lead(
        source="inbound_diagnostico",
        business=business,
        category=category,
        city="",
        commune=commune,
        website_url=website_url,
        opportunity_score=88 if not website_url else 62,
        contact_email=email,
        contact_email_source_url=f"{get_settings().public_base_url.rstrip('/')}/diagnostico-gratis",
        consent=consent_record("diagnostico", text_version(consent_text), ip),
        status="nuevo",
        estimated_value_clp=price,
        high_value=category in HIGH_VALUE_CATEGORIES,
        tone=tone_for(category),
    )
    LeadRepository(session).add(lead)
    transition_lead(
        session,
        lead,
        "diagnosticado",
        actor="sistema",
        reason="diagnóstico gratis con consentimiento",
    )
    return {"id": lead.id, "status": lead.status}


def submit_contacto(
    session: Session,
    *,
    name: str,
    email: str,
    message: str,
    ip: str,
) -> dict[str, str]:
    lead = Lead(
        source="inbound_contacto",
        business=name,
        category="pendiente",
        city="",
        commune="",
        opportunity_score=0,
        contact_email=email,
        consent=consent_record("contacto", "contacto-v1", ip),
        status="respondio",
        estimated_value_clp=0,
        high_value=False,
        tone="tu",
        diagnosis={"markdown": message, "message": message},
    )
    LeadRepository(session).add(lead)
    session.add(
        Message(
            lead_id=lead.id,
            thread_id=lead.id,
            direction="in",
            channel="web_form",
            status="received",
            body_text=message,
        )
    )
    EventRepository(session).append(
        agent="api",
        level="info",
        message="contacto inbound con consentimiento",
        lead_id=lead.id,
    )
    session.flush()
    return {"id": lead.id, "status": lead.status}


def submit_rights(session: Session, *, kind: str, email: str, details: str) -> dict[str, str]:
    if kind not in _RIGHTS:
        raise ApiError(422, "validation_error", "tipo de solicitud inválido")
    row = DataRequestRepository(session).add(kind=kind, requester_email=email, details=details)
    return {"id": row.id, "status": row.status}


def checkout(
    session: Session,
    provider: PaymentProvider,
    *,
    package_code: str,
    lead_id: str | None,
) -> dict[str, str]:
    price = _price_of(session, package_code)
    if price is None:
        raise ApiError(422, "validation_error", "el paquete se cotiza con revisión humana")
    if not lead_id:
        raise ApiError(422, "validation_error", "falta el lead")
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise ApiError(404, "not_found", "lead no encontrado")
    settings = get_settings()
    net, iva, total = split_iva(price, settings.prices_include_iva)
    deposit = total * settings.deposit_percent // 100
    order = Order(
        lead_id=lead.id,
        package_code=package_code,
        amount_clp=net,
        iva_clp=iva,
        total_clp=total,
        deposit_percent=settings.deposit_percent,
        status="pending",
    )
    session.add(order)
    session.flush()
    title = next(item["name"] for item in PACKAGES if item["code"] == package_code)
    preference = provider.create_preference(order.id, str(title), deposit or total)
    order.checkout_url = preference.checkout_url
    order.provider_preference_id = preference.id
    session.add(order)
    session.flush()
    return {"order_id": order.id, "checkout_url": preference.checkout_url}


def apply_baja(session: Session, token: str) -> dict[str, bool]:
    lead = session.get(Lead, read_baja_token(token))
    if lead is None:
        raise ApiError(404, "not_found", "token desconocido")
    repo = SuppressionRepository(session)
    if lead.contact_email:
        repo.add("email", lead.contact_email, reason="baja", source="unsubscribe")
        if "@" in lead.contact_email:
            domain = lead.contact_email.split("@", 1)[1]
            if domain:
                repo.add("domain", domain, reason="baja", source="unsubscribe")
    if "opt_out" in TRANSITIONS.get(lead.status, frozenset()):
        transition_lead(session, lead, "opt_out", actor="sistema", reason="baja solicitada")
    EventRepository(session).append(
        agent="api",
        level="info",
        message="baja solicitada",
        lead_id=lead.id,
    )
    return {"ok": True}


def load_demo(session: Session, token: str) -> tuple[int, str | dict[str, Any], bool]:
    artifact = session.scalar(select(Artifact).where(Artifact.public_token == token))
    missing = error_body("not_found", "demo no encontrada")
    if artifact is None:
        return 404, missing, False
    if artifact.expires_at is not None and artifact.expires_at <= datetime.now(UTC):
        return 410, error_body("gone", "la demo expiró"), False
    raw = Path(artifact.path)
    path = raw if raw.is_absolute() else ENGINE_DIR / raw
    if not path.is_file():
        return 404, missing, False
    return 200, path.read_text(encoding="utf-8"), True


def project_by_token(session: Session, token: str) -> Project:
    project = session.scalar(select(Project).where(Project.portal_token == token))
    if project is None:
        raise ApiError(404, "not_found", "proyecto no encontrado")
    return project


def project_public(session: Session, token: str) -> dict[str, Any]:
    project = project_by_token(session, token)
    lead = session.get(Lead, project.lead_id)
    return {
        "status": project.status,
        "business": lead.business if lead is not None else "",
        "revisions_used": project.revisions_used,
        "max_revisions": project.max_revisions,
        "preview_url": project.deploy_url,
    }


def save_intake(session: Session, token: str, payload: dict[str, Any]) -> dict[str, bool]:
    project = project_by_token(session, token)
    project.intake = payload
    session.add(project)
    session.flush()
    return {"ok": True}


def save_feedback(session: Session, token: str, text: str) -> dict[str, str]:
    project = project_by_token(session, token)
    current = dict(project.intake) if isinstance(project.intake, dict) else {}
    notes = list(current.get("feedback") or [])
    notes.append({"text": text, "ts": datetime.now(UTC).isoformat()})
    current["feedback"] = notes
    project.intake = current
    if project.revisions_used < project.max_revisions:
        project.revisions_used += 1
        session.add(project)
        session.flush()
        return {"id": project.id, "status": "accepted"}
    session.add(
        Approval(
            lead_id=project.lead_id,
            kind="fuera_de_alcance",
            payload={"text": text},
            status="pending",
        )
    )
    session.add(project)
    session.flush()
    return {"id": project.id, "status": "fuera_de_alcance"}


def approve_project_public(session: Session, token: str) -> dict[str, str]:
    project = project_by_token(session, token)
    session.execute(update(Project).where(Project.id == project.id).values(status="aprobado"))
    session.flush()
    lead = session.get(Lead, project.lead_id)
    if lead is not None and lead.status == "en_revision_cliente":
        transition_lead(
            session,
            lead,
            "entregado",
            actor="humano",
            reason="el cliente aprobó el proyecto",
        )
    return {"id": project.id, "status": "aprobado"}


def domain_authorized(session: Session, domain: str) -> bool:
    try:
        normalized = normalize_contact("domain", domain)
    except ValueError:
        return False
    if not normalized:
        return False
    rows = session.scalars(select(Project).where(Project.domain.is_not(None))).all()
    for project in rows:
        if not project.domain:
            continue
        try:
            current = normalize_contact("domain", project.domain)
        except ValueError:
            continue
        if current == normalized and project.status in {"aprobado", "publicado"}:
            return True
    return False


def _claim_webhook(session: Session, provider: str, event_id: str) -> bool:
    exists = session.scalar(
        select(WebhookEvent.id).where(
            WebhookEvent.provider == provider,
            WebhookEvent.event_id == event_id,
        )
    )
    if exists is not None:
        return False
    session.add(WebhookEvent(provider=provider, event_id=event_id))
    session.flush()
    return True


def _find_lead_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("lead_id"), str):
        return str(payload["lead_id"])
    meta = payload.get("metadata")
    if isinstance(meta, dict) and isinstance(meta.get("lead_id"), str):
        return str(meta["lead_id"])
    nested = payload.get("payload")
    if isinstance(nested, dict):
        return _find_lead_id(nested)
    return None


def _maybe_schedule(session: Session, body: bytes) -> None:
    try:
        import json

        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return
    lead_id = _find_lead_id(payload)
    if not lead_id:
        return
    lead = session.get(Lead, lead_id)
    if lead is None:
        return
    if "agendado" in TRANSITIONS.get(lead.status, frozenset()):
        transition_lead(session, lead, "agendado", actor="webhook", reason="agenda confirmada")


def accept_signed_event(
    session: Session,
    provider: str,
    event_id: str,
    body: bytes,
) -> dict[str, Any]:
    if not _claim_webhook(session, provider, event_id):
        return {"ok": True, "duplicate": True}
    if provider in {"calcom", "calendly"}:
        _maybe_schedule(session, body)
    return {"ok": True, "duplicate": False}


def apply_payment(session: Session, fact: PaymentFact) -> dict[str, Any]:
    existing = session.scalar(
        select(Payment).where(Payment.provider_payment_id == fact.provider_payment_id)
    )
    if existing is not None:
        return {
            "ok": True,
            "duplicate": True,
            "payment_id": existing.id,
            "order_id": existing.order_id,
        }
    order = session.get(Order, fact.order_id) if fact.order_id else None
    if order is None:
        if not fact.lead_id or session.get(Lead, fact.lead_id) is None:
            return {"ok": True, "ignored": True}
        net, iva, total = split_iva(fact.amount_clp, get_settings().prices_include_iva)
        order = Order(
            lead_id=str(fact.lead_id),
            package_code=fact.package_code or "landing_esencial",
            amount_clp=net,
            iva_clp=iva,
            total_clp=total,
            deposit_percent=get_settings().deposit_percent,
            status="pending",
            provider_preference_id=fact.provider_payment_id,
        )
        session.add(order)
        session.flush()
    payment = Payment(
        order_id=order.id,
        provider="mercadopago",
        provider_payment_id=fact.provider_payment_id,
        status=fact.status,
        amount_clp=fact.amount_clp,
        raw=fact.raw or {"id": fact.provider_payment_id, "source": "fetch_payment"},
    )
    try:
        session.add(payment)
        session.flush()
    except IntegrityError:
        session.rollback()
        return {"ok": True, "duplicate": True}
    if not _claim_webhook(session, "mercadopago", fact.provider_payment_id):
        return {"ok": True, "duplicate": True, "payment_id": payment.id, "order_id": order.id}
    if fact.status in _PAID:
        session.execute(update(Order).where(Order.id == order.id).values(status="paid"))
        project = session.scalar(select(Project).where(Project.order_id == order.id))
        if project is None:
            session.add(
                Project(
                    order_id=order.id,
                    lead_id=order.lead_id,
                    status="intake_pendiente",
                    revisions_used=0,
                    max_revisions=revisions_for(order.package_code),
                )
            )
        lead = session.get(Lead, order.lead_id)
        if lead is not None and lead.status == "propuesta":
            transition_lead(
                session,
                lead,
                "pagado",
                actor="webhook",
                reason="pago verificado en el proveedor",
            )
        pending_task = session.scalar(
            select(Approval.id).where(
                Approval.lead_id == order.lead_id,
                Approval.kind == "tarea_manual",
                Approval.status == "pending",
            )
        )
        if pending_task is None:
            session.add(
                Approval(
                    lead_id=order.lead_id,
                    kind="tarea_manual",
                    payload={"note": "emitir documento tributario", "order_id": order.id},
                    status="pending",
                )
            )
    session.flush()
    return {"ok": True, "duplicate": False, "payment_id": payment.id, "order_id": order.id}


def list_leads(
    session: Session,
    *,
    status: str | None,
    q: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    page = 1 if page < 1 else page
    page_size = 20 if page_size < 1 else min(page_size, 100)
    filters: list[Any] = []
    if status:
        filters.append(Lead.status == status)
    if q and q.strip():
        needle = f"%{q.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Lead.business).like(needle),
                func.lower(Lead.commune).like(needle),
                func.lower(func.coalesce(Lead.contact_email, "")).like(needle),
            )
        )
    total = session.scalar(select(func.count()).select_from(Lead).where(*filters)) or 0
    rows = session.scalars(
        select(Lead)
        .where(*filters)
        .order_by(Lead.created_at.desc(), Lead.id.asc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return {
        "items": [lead_dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": int(total),
    }


def lead_detail(session: Session, lead_id: str) -> dict[str, Any]:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise ApiError(404, "not_found", "lead no encontrado")
    events = session.scalars(
        select(LeadEvent).where(LeadEvent.lead_id == lead.id).order_by(LeadEvent.ts.asc())
    ).all()
    messages = session.scalars(
        select(Message).where(Message.lead_id == lead.id).order_by(Message.created_at.asc())
    ).all()
    artifacts = session.scalars(select(Artifact).where(Artifact.lead_id == lead.id)).all()
    detail = lead_dict(lead)
    detail["timeline"] = [timeline_dict(item) for item in events]
    detail["messages"] = [message_dict(item) for item in messages]
    detail["artifacts"] = [artifact_dict(item) for item in artifacts]
    detail["website_audit"] = lead.website_audit
    detail["diagnosis"] = lead.diagnosis
    return detail


def patch_lead(session: Session, lead_id: str, payload: LeadPatch) -> dict[str, Any]:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise ApiError(404, "not_found", "lead no encontrado")
    if "tone" in payload.model_fields_set and payload.tone is not None:
        if payload.tone not in {"tu", "usted"}:
            raise ApiError(422, "validation_error", "tono inválido")
        lead.tone = payload.tone
    if "next_action_at" in payload.model_fields_set:
        lead.next_action_at = payload.next_action_at
    LeadRepository(session).save(lead)
    return lead_dict(lead)


def transition_from_admin(session: Session, lead_id: str, to: str, reason: str) -> dict[str, Any]:
    lead = session.get(Lead, lead_id)
    if lead is None:
        raise ApiError(404, "not_found", "lead no encontrado")
    transition_lead(session, lead, to, actor="humano", reason=reason)
    return lead_dict(lead)


def list_approvals(session: Session, status: str | None) -> list[dict[str, Any]]:
    rows = ApprovalRepository(session).list(status=status)
    return [
        {
            "id": row.id,
            "lead_id": row.lead_id,
            "kind": row.kind,
            "status": row.status,
            "payload": row.payload if isinstance(row.payload, dict) else {},
        }
        for row in rows
    ]


def approve_hitl(session: Session, approval_id: str, email: str) -> dict[str, Any]:
    approval = session.get(Approval, approval_id)
    if approval is None:
        raise ApiError(404, "not_found", "aprobación no encontrada")
    if approval.status != "pending":
        raise ApiError(409, "conflict", "la aprobación no está pendiente")
    lead = session.get(Lead, approval.lead_id)
    if lead is None:
        raise ApiError(404, "not_found", "lead no encontrado")
    transition_lead(session, lead, "paused_from", actor="humano", reason="aprobación humana")
    session.execute(
        update(Approval)
        .where(Approval.id == approval.id)
        .values(status="approved", decided_by=email, decided_at=utcnow())
    )
    session.flush()
    session.refresh(lead)
    return lead_dict(lead)


def reject_hitl(session: Session, approval_id: str, email: str, note: str | None) -> dict[str, str]:
    approval = session.get(Approval, approval_id)
    if approval is None:
        raise ApiError(404, "not_found", "aprobación no encontrada")
    if approval.status != "pending":
        raise ApiError(409, "conflict", "la aprobación no está pendiente")
    session.execute(
        update(Approval)
        .where(Approval.id == approval.id)
        .values(status="rejected", decided_by=email, decided_at=utcnow(), decision_note=note)
    )
    session.flush()
    return {"id": approval.id, "status": "rejected"}


def edit_hitl(
    session: Session,
    approval_id: str,
    email: str,
    *,
    body_text: str | None,
    subject: str | None,
    message_id: str | None,
) -> dict[str, str]:
    approval = session.get(Approval, approval_id)
    if approval is None:
        raise ApiError(404, "not_found", "aprobación no encontrada")
    if approval.status not in {"pending", "edited"}:
        raise ApiError(409, "conflict", "la aprobación no se puede editar")
    payload = approval.payload if isinstance(approval.payload, dict) else {}
    target = message_id or payload.get("message_id")
    if not isinstance(target, str) or not target:
        raise ApiError(404, "not_found", "mensaje no encontrado")
    message = session.get(Message, target)
    if message is None or message.lead_id != approval.lead_id:
        raise ApiError(404, "not_found", "mensaje no encontrado")
    values: dict[str, Any] = {"status": "checking"}
    if body_text is not None:
        values["body_text"] = body_text
    if subject is not None:
        values["subject"] = subject
    session.execute(update(Message).where(Message.id == message.id).values(**values))
    session.execute(
        update(Approval)
        .where(Approval.id == approval.id)
        .values(status="edited", decided_by=email, decided_at=utcnow())
    )
    session.flush()
    session.refresh(message)
    return {"id": approval.id, "status": "edited", "message_status": message.status}


def list_messages(session: Session, lead_id: str | None) -> list[dict[str, Any]]:
    rows = MessageRepository(session).list(lead_id=lead_id, limit=200)
    return [message_dict(row) for row in rows]


def manual_queue(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Message)
        .where(
            Message.status == "manual_pending",
            Message.channel.in_(("instagram", "linkedin")),
        )
        .order_by(Message.created_at.asc())
    ).all()
    return [message_dict(row) for row in rows]


def mark_manual_sent(session: Session, message_id: str) -> dict[str, Any]:
    message = session.get(Message, message_id)
    if message is None:
        raise ApiError(404, "not_found", "mensaje no encontrado")
    if message.status != "manual_pending":
        raise ApiError(409, "conflict", "el mensaje no está en la cola manual")
    session.execute(
        update(Message)
        .where(Message.id == message.id)
        .values(status="manual_sent", sent_at=utcnow())
    )
    session.flush()
    session.refresh(message)
    return message_dict(message)


def threads(session: Session) -> list[dict[str, str]]:
    rows = session.scalars(select(Message).order_by(Message.created_at.asc())).all()
    grouped: dict[str, dict[str, str]] = {}
    for row in rows:
        grouped[row.thread_id] = {
            "id": row.thread_id,
            "lead_id": row.lead_id,
            "last_message": row.body_text,
        }
    return list(grouped.values())


def reply_thread(session: Session, thread_id: str, body_text: str) -> dict[str, str]:
    last = session.scalar(
        select(Message).where(Message.thread_id == thread_id).order_by(Message.created_at.desc())
    )
    if last is None:
        raise ApiError(404, "not_found", "hilo no encontrado")
    message = Message(
        lead_id=last.lead_id,
        thread_id=thread_id,
        direction="out",
        channel=last.channel,
        status="checking",
        body_text=body_text,
    )
    session.add(message)
    session.flush()
    return {"id": message.id, "status": message.status}


def _prompt_version(text: str) -> str:
    for line in text.splitlines()[:50]:
        stripped = line.strip()
        if stripped.lower().startswith("version:"):
            return stripped.split(":", 1)[1].strip()
    return ""


def agent_rows(session: Session) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((ENGINE_DIR / "prompts").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        runs = JobRunRepository(session).list(job=path.stem, limit=1)
        last_run = runs[0] if runs else None
        last_error = last_run.error if last_run is not None and last_run.error else None
        if last_error is None:
            event = session.scalar(
                select(Event)
                .where(Event.agent == path.stem, Event.level == "error")
                .order_by(Event.ts.desc())
                .limit(1)
            )
            if event is not None:
                last_error = event.message
        rows.append(
            {
                "name": path.stem,
                "prompt_name": path.stem,
                "prompt_version": _prompt_version(text),
                "prompt_markdown": text,
                "last_run_at": last_run.started_at.isoformat() if last_run is not None else None,
                "last_error": last_error,
            }
        )
    return rows


def enqueue_action(session: Session, name: str, email: str) -> dict[str, str]:
    event = EventRepository(session).append(
        agent="api",
        level="info",
        message=f"job encolado: {name}",
        meta={"job": name, "by": email},
    )
    return {"id": event.id, "status": "queued"}


def list_events(
    session: Session,
    *,
    level: str | None,
    agent: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    capped = 100 if limit < 1 else min(limit, 500)
    stmt = select(Event).order_by(Event.ts.desc()).limit(capped)
    if level:
        stmt = stmt.where(Event.level == level)
    if agent:
        stmt = stmt.where(Event.agent == agent)
    return [event_dict(row) for row in session.scalars(stmt).all()]


def sse_body(session: Session) -> str:
    rows = EventRepository(session).list(limit=1)
    chunks = [": ok\n\n"]
    if rows:
        import json

        chunks.append(f"data: {json.dumps(event_dict(rows[0]), ensure_ascii=False)}\n\n")
    return "".join(chunks)


def metrics(session: Session) -> dict[str, Any]:
    revenue = session.scalar(
        select(func.coalesce(func.sum(Payment.amount_clp), 0)).where(Payment.status.in_(_PAID))
    )
    cost = session.scalar(select(func.coalesce(func.sum(LlmCall.cost_usd), 0)))
    start = _start_of_local_day(datetime.now(UTC))
    tokens = session.scalar(
        select(func.coalesce(func.sum(LlmCall.tokens_in + LlmCall.tokens_out), 0)).where(
            LlmCall.ts >= start
        )
    )
    funnel = dict.fromkeys(sorted(STATUSES), 0)
    grouped = session.execute(select(Lead.status, func.count()).group_by(Lead.status)).all()
    for status_name, count in grouped:
        funnel[str(status_name)] = int(count)
    pipeline: dict[str, int] = {}
    for status_name, count in session.execute(
        select(Order.status, func.count()).group_by(Order.status)
    ):
        pipeline[str(status_name)] = int(count)
    sent: dict[str, int] = {}
    inbound: dict[str, int] = {}
    buckets = session.execute(
        select(Message.channel, Message.direction, Message.status, func.count()).group_by(
            Message.channel, Message.direction, Message.status
        )
    ).all()
    for channel, direction, status_name, count in buckets:
        if direction == "out" and status_name in _SENT:
            sent[str(channel)] = sent.get(str(channel), 0) + int(count)
        if direction == "in" and status_name == "received":
            inbound[str(channel)] = inbound.get(str(channel), 0) + int(count)
    rates = {
        channel: round(inbound.get(channel, 0) / total, 4)
        for channel, total in sent.items()
        if total
    }
    return {
        "revenue_clp": int(revenue or 0),
        "llm_cost_usd": float(Decimal(str(cost or 0))),
        "tokens_today": int(tokens or 0),
        "response_rate_by_channel": rates,
        "funnel": funnel,
        "pipeline": pipeline,
        "quotas": read_settings_view(session)["quotas"],
    }


def list_orders(session: Session) -> list[dict[str, Any]]:
    return [order_dict(row) for row in OrderRepository(session).list(limit=200)]


def list_projects(session: Session) -> list[dict[str, Any]]:
    return [project_dict(row) for row in ProjectRepository(session).list(limit=200)]


def patch_project(session: Session, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    project = session.get(Project, project_id)
    if project is None:
        raise ApiError(404, "not_found", "proyecto no encontrado")
    data = dict(payload)
    new_status = data.pop("status", None)
    for key in ("domain", "deploy_url", "max_revisions", "revisions_used"):
        if key in data:
            setattr(project, key, data[key])
    if "intake" in data:
        project.intake = data["intake"]
    session.add(project)
    session.flush()
    if new_status is not None:
        if new_status not in _PROJECT_STATUSES:
            raise ApiError(422, "validation_error", "estado de proyecto inválido")
        session.execute(update(Project).where(Project.id == project.id).values(status=new_status))
        session.flush()
        session.refresh(project)
    return project_dict(project)


def list_suppression(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(Suppression).order_by(Suppression.created_at.desc())).all()
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "value_hash": row.value_hash,
            "reason": row.reason,
            "source": row.source,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def add_suppression(session: Session, kind: str, value: str, reason: str) -> dict[str, str]:
    if kind not in CONTACT_KINDS:
        raise ApiError(422, "validation_error", "kind de supresión desconocido")
    row = SuppressionRepository(session).add(kind, value, reason=reason, source="admin")
    return {"id": row.id, "value_hash": row.value_hash}


def delete_suppression(session: Session, row_id: str) -> None:
    row = session.get(Suppression, row_id)
    if row is None:
        raise ApiError(404, "not_found", "supresión no encontrada")
    session.delete(row)
    session.flush()


def list_data_requests(session: Session) -> list[dict[str, Any]]:
    rows = DataRequestRepository(session).list(limit=200)
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "requester_email": row.requester_email,
            "details": row.details,
            "status": row.status,
            "due_at": row.due_at.isoformat(),
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        }
        for row in rows
    ]


def patch_data_request(session: Session, request_id: str, status_name: str) -> dict[str, str]:
    if status_name not in {"open", "done", "rejected"}:
        raise ApiError(422, "validation_error", "estado inválido")
    row = session.get(DataRequest, request_id)
    if row is None:
        raise ApiError(404, "not_found", "solicitud no encontrada")
    values: dict[str, Any] = {"status": status_name}
    if status_name in {"done", "rejected"}:
        values["resolved_at"] = utcnow()
    session.execute(update(DataRequest).where(DataRequest.id == row.id).values(**values))
    session.flush()
    return {"id": row.id, "status": status_name}


def meta_categories() -> list[dict[str, str]]:
    return [
        {"slug": slug, "label": label, "theme": theme, "tone": tone}
        for slug, label, theme, tone in CATEGORIES
    ]


def meta_statuses() -> dict[str, Any]:
    transitions = {name: sorted(targets) for name, targets in TRANSITIONS.items()}
    transitions["revision"] = sorted(set(transitions.get("revision", [])) | {"paused_from"})
    return {"statuses": sorted(STATUSES), "transitions": transitions}


def webhook_event_id(headers: dict[str, str], body: bytes) -> str:
    for key in ("x-request-id", "svix-id", "webhook-id"):
        if headers.get(key):
            return headers[key]
    return hashlib.sha256(body).hexdigest()


def resend_secret() -> str:
    return os.environ.get("RESEND_WEBHOOK_SECRET", "").strip()
