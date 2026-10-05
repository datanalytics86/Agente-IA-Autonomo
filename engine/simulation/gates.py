"""Compuertas humanas de la simulación. El worker no aprueba ni cobra solo."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import PaymentFact as ApiPayment
from api.services import accept_signed_event, apply_payment, approve_project_public, save_intake
from core.states import TRANSITIONS
from db.models import Lead, Message, Order, Project
from simulation.providers import SentRecord, World
from worker.persist import patch_fields
from worker.ports import Ports

_BUY = frozenset({"interesado", "agendar"})
_INTAKE = {
    "objetivo": "Mostrar la información pública del negocio",
    "servicios": "Los servicios que el negocio ya publica",
}


def sync_outreach(session: Session, world: World) -> None:
    """El pitcher de demo no pasa por el transporte. El buzón falso necesita el envío."""
    known = {item.message_id for item in world.sent}
    rows = session.execute(
        select(Message, Lead)
        .join(Lead, Lead.id == Message.lead_id)
        .where(
            Message.channel == "email_outreach",
            Message.direction == "out",
            Message.status == "sent",
        )
        .order_by(Lead.business.asc(), Message.sequence_step.asc(), Message.id.asc())
    ).all()
    for message, lead in rows:
        if message.id in known:
            continue
        email = (lead.contact_email or "").lower()
        role = world.roles.get(email, "silencio")
        status = "sent"
        if role == "bounce":
            _record_bounce(session, message, lead.contact_email or email)
            status = "bounced"
        world.sent.append(SentRecord(message.id, email, status, role))


def _record_bounce(session: Session, message: Message, email: str) -> None:
    provider_id = message.provider_message_id or f"fake-{message.id}"
    if message.provider_message_id != provider_id:
        patch_fields(session, message, provider_message_id=provider_id)
    body = json.dumps(
        {"type": "email.bounced", "email_id": provider_id, "to": email},
        ensure_ascii=False,
    ).encode("utf-8")
    accept_signed_event(session, "email", f"bounce-{message.id}", body)


def apply_bookings(session: Session, ports: Ports) -> None:
    """Agenda solo a quien ya respondió con intención de compra y puede pasar a agendado."""
    ready: set[str] = set()
    leads = session.scalars(select(Lead).order_by(Lead.business.asc(), Lead.id.asc())).all()
    for lead in leads:
        if not _can_book(session, lead):
            continue
        ports.bookings.link_for(lead.id)
        ready.add(lead.id)
    for event in ports.bookings.poll():
        if event.lead_id not in ready:
            continue
        body = json.dumps(
            {"lead_id": event.lead_id, "start": event.start.isoformat()},
            ensure_ascii=False,
        ).encode("utf-8")
        accept_signed_event(session, "calcom", event.provider_event_id, body)
        acknowledge = getattr(ports.bookings, "acknowledge", None)
        if callable(acknowledge):
            acknowledge(event.lead_id)


def drive_sales(session: Session, ports: Ports) -> None:
    """Anticipo, intake, aprobación del cliente y saldo. El alto valor no entra."""
    _pay_deposits(session, ports)
    _submit_intakes(session)
    _approve_ready(session)
    _pay_balances(session)


def _can_book(session: Session, lead: Lead) -> bool:
    if lead.high_value or lead.source == "sistema" or _blocked_scenario(lead):
        return False
    if "agendado" not in TRANSITIONS.get(lead.status, frozenset()):
        return False
    return _buy_intent(session, lead.id)


def _buy_intent(session: Session, lead_id: str) -> bool:
    rows = session.scalars(
        select(Message)
        .where(Message.lead_id == lead_id, Message.direction == "in")
        .order_by(Message.created_at.asc())
    ).all()
    return any(row.intent in _BUY for row in rows)


def _blocked_scenario(lead: Lead) -> bool:
    audit = lead.website_audit if isinstance(lead.website_audit, dict) else {}
    return audit.get("scenario") in {"injection", "opt_out", "alto_valor"}


def _pay_deposits(session: Session, ports: Ports) -> None:
    for fact in ports.payments.poll():
        order = session.get(Order, fact.order_id)
        if order is None or order.status != "pending":
            continue
        lead = session.get(Lead, order.lead_id)
        if lead is None or lead.high_value or _blocked_scenario(lead):
            continue
        apply_payment(
            session,
            ApiPayment(
                provider_payment_id=fact.provider_payment_id,
                status=fact.status,
                amount_clp=fact.amount_clp,
                order_id=order.id,
                lead_id=order.lead_id,
            ),
        )


def _submit_intakes(session: Session) -> None:
    leads = session.scalars(
        select(Lead).where(Lead.status == "pagado").order_by(Lead.business.asc(), Lead.id.asc())
    ).all()
    for lead in leads:
        if lead.high_value or _blocked_scenario(lead):
            continue
        project = session.scalar(select(Project).where(Project.lead_id == lead.id))
        if project is None or not project.portal_token:
            continue
        save_intake(session, project.portal_token, dict(_INTAKE))


def _approve_ready(session: Session) -> None:
    leads = session.scalars(
        select(Lead)
        .where(Lead.status == "en_revision_cliente")
        .order_by(Lead.business.asc(), Lead.id.asc())
    ).all()
    for lead in leads:
        if lead.high_value or _blocked_scenario(lead):
            continue
        project = session.scalar(select(Project).where(Project.lead_id == lead.id))
        if project is None or not project.portal_token:
            continue
        order = session.get(Order, project.order_id)
        if order is None or order.status not in {"deposit_paid", "paid"}:
            continue
        intake = project.intake if isinstance(project.intake, dict) else {}
        if order.status == "deposit_paid" and intake.get("client_approved") is True:
            continue
        approve_project_public(session, project.portal_token)


def _pay_balances(session: Session) -> None:
    orders = session.scalars(select(Order).where(Order.status == "deposit_paid")).all()
    for order in sorted(orders, key=lambda item: item.id):
        lead = session.get(Lead, order.lead_id)
        if lead is None or lead.high_value or _blocked_scenario(lead):
            continue
        project = session.scalar(select(Project).where(Project.order_id == order.id))
        intake = project.intake if project is not None and isinstance(project.intake, dict) else {}
        if intake.get("client_approved") is not True:
            continue
        deposit = order.total_clp * order.deposit_percent // 100
        balance = order.total_clp - deposit
        if balance <= 0:
            continue
        apply_payment(
            session,
            ApiPayment(
                provider_payment_id=f"saldo-{order.id}",
                status="approved",
                amount_clp=balance,
                order_id=order.id,
                lead_id=order.lead_id,
            ),
        )
