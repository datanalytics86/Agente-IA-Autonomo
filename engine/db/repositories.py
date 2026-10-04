"""Repositorios. El resto del sistema no ejecuta SQL suelto."""

from __future__ import annotations

import builtins
from datetime import UTC, datetime, timedelta, tzinfo
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from core.config import get_settings
from core.errors import DuplicateLeadError
from db.models import (
    Approval,
    Artifact,
    DataRequest,
    Event,
    JobRun,
    Lead,
    LlmCall,
    Message,
    Order,
    Payment,
    Project,
    Setting,
    Suppression,
    utcnow,
)
from db.normalize import contact_hash, normalize_business

_DATA_REQUEST_DAYS = 30


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _start_of_local_day(moment: datetime) -> datetime:
    current = _as_utc(moment)
    zone: tzinfo
    try:
        zone = ZoneInfo(get_settings().tz)
    except ZoneInfoNotFoundError:
        zone = UTC
    local = current.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


def due_messages_statement(now: datetime, limit: int, *, dialect_name: str) -> Select[Message]:
    """En Postgres agrega FOR UPDATE SKIP LOCKED. SQLite no lo soporta."""
    stmt = (
        select(Message)
        .where(Message.status == "queued", Message.scheduled_at <= now)
        .order_by(Message.scheduled_at.asc())
        .limit(limit)
    )
    if dialect_name == "postgresql":
        return stmt.with_for_update(skip_locked=True)
    return stmt


class LeadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, lead_id: str) -> Lead | None:
        return self.session.get(Lead, lead_id)

    def list(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Lead]:
        stmt = select(Lead)
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        stmt = stmt.order_by(Lead.created_at.desc(), Lead.id.asc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def add(self, lead: Lead) -> Lead:
        self._ensure_unique_business(lead)
        self.session.add(lead)
        self.session.flush()
        return lead

    def save(self, lead: Lead) -> Lead:
        self._ensure_unique_business(lead)
        lead.updated_at = utcnow()
        self.session.add(lead)
        self.session.flush()
        return lead

    def _ensure_unique_business(self, lead: Lead) -> None:
        if lead.anonymized_at is not None:
            return
        target = normalize_business(lead.business)
        stmt = select(Lead).where(
            Lead.commune == lead.commune,
            Lead.anonymized_at.is_(None),
            Lead.id != lead.id,
        )
        for other in self.session.scalars(stmt):
            if normalize_business(other.business) == target:
                raise DuplicateLeadError(
                    f"ya existe un lead activo para {lead.business!r} en {lead.commune}"
                )


class MessageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, message_id: str) -> Message | None:
        return self.session.get(Message, message_id)

    def add(self, message: Message) -> Message:
        self.session.add(message)
        self.session.flush()
        return message

    def list(self, *, lead_id: str | None = None, limit: int = 100) -> list[Message]:
        stmt = select(Message)
        if lead_id is not None:
            stmt = stmt.where(Message.lead_id == lead_id)
        stmt = stmt.order_by(Message.created_at.asc()).limit(limit)
        return list(self.session.scalars(stmt).all())

    def claim_due(self, *, now: datetime | None = None, limit: int = 50) -> builtins.list[Message]:
        """Mensajes queued con scheduled_at vencido.

        Postgres: SELECT … FOR UPDATE SKIP LOCKED. SQLite: la transacción de
        get_engine ya es BEGIN IMMEDIATE, así que el lock cubre estas filas.
        """
        moment = _as_utc(now or utcnow())
        dialect_name = self.session.get_bind().dialect.name
        stmt = due_messages_statement(moment, limit, dialect_name=dialect_name)
        return list(self.session.scalars(stmt).all())


class ApprovalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, approval_id: str) -> Approval | None:
        return self.session.get(Approval, approval_id)

    def add(self, approval: Approval) -> Approval:
        self.session.add(approval)
        self.session.flush()
        return approval

    def list(self, *, status: str | None = None, limit: int = 100) -> list[Approval]:
        stmt = select(Approval)
        if status is not None:
            stmt = stmt.where(Approval.status == status)
        stmt = stmt.order_by(Approval.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class ArtifactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, artifact_id: str) -> Artifact | None:
        return self.session.get(Artifact, artifact_id)

    def add(self, artifact: Artifact) -> Artifact:
        self.session.add(artifact)
        self.session.flush()
        return artifact

    def list(self, *, lead_id: str | None = None, limit: int = 100) -> list[Artifact]:
        stmt = select(Artifact)
        if lead_id is not None:
            stmt = stmt.where(Artifact.lead_id == lead_id)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, order_id: str) -> Order | None:
        return self.session.get(Order, order_id)

    def add(self, order: Order) -> Order:
        self.session.add(order)
        self.session.flush()
        return order

    def list(self, *, lead_id: str | None = None, limit: int = 100) -> list[Order]:
        stmt = select(Order)
        if lead_id is not None:
            stmt = stmt.where(Order.lead_id == lead_id)
        stmt = stmt.order_by(Order.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class PaymentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, payment_id: str) -> Payment | None:
        return self.session.get(Payment, payment_id)

    def add(self, payment: Payment) -> Payment:
        existing = self.session.scalar(
            select(Payment).where(Payment.provider_payment_id == payment.provider_payment_id)
        )
        if existing is not None:
            return existing
        self.session.add(payment)
        self.session.flush()
        return payment

    def list(self, *, order_id: str | None = None, limit: int = 100) -> list[Payment]:
        stmt = select(Payment)
        if order_id is not None:
            stmt = stmt.where(Payment.order_id == order_id)
        stmt = stmt.order_by(Payment.received_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, project_id: str) -> Project | None:
        return self.session.get(Project, project_id)

    def add(self, project: Project) -> Project:
        self.session.add(project)
        self.session.flush()
        return project

    def list(self, *, lead_id: str | None = None, limit: int = 100) -> list[Project]:
        stmt = select(Project)
        if lead_id is not None:
            stmt = stmt.where(Project.lead_id == lead_id)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())


class SuppressionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def contains(self, kind: str, raw_value: str) -> bool:
        if not raw_value or not raw_value.strip():
            return False
        digest = contact_hash(kind, raw_value)
        stmt = select(Suppression.id).where(
            Suppression.kind == kind,
            Suppression.value_hash == digest,
        )
        return self.session.scalar(stmt) is not None

    def add(self, kind: str, raw_value: str, *, reason: str, source: str) -> Suppression:
        if not raw_value or not raw_value.strip():
            raise ValueError("el valor a suprimir está vacío")
        digest = contact_hash(kind, raw_value)
        existing = self.session.scalar(
            select(Suppression).where(
                Suppression.kind == kind,
                Suppression.value_hash == digest,
            )
        )
        if existing is not None:
            return existing
        row = Suppression(kind=kind, value_hash=digest, reason=reason, source=source)
        self.session.add(row)
        self.session.flush()
        return row


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str, default: Any = None) -> Any:
        row = self.session.get(Setting, key)
        if row is None:
            return default
        return row.value

    def put(self, key: str, value: Any, *, updated_by: str) -> Setting:
        row = self.session.get(Setting, key)
        now = utcnow()
        if row is None:
            row = Setting(key=key, value=value, updated_by=updated_by, updated_at=now)
            self.session.add(row)
        else:
            row.value = value
            row.updated_by = updated_by
            row.updated_at = now
        self.session.flush()
        return row


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(
        self,
        *,
        agent: str,
        level: str,
        message: str,
        lead_id: str | None = None,
        meta: dict[str, Any] | None = None,
        ts: datetime | None = None,
    ) -> Event:
        row = Event(
            ts=ts or utcnow(),
            agent=agent,
            level=level,
            message=message,
            lead_id=lead_id,
            meta=meta,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list(
        self,
        *,
        limit: int = 100,
        lead_id: str | None = None,
        level: str | None = None,
    ) -> list[Event]:
        stmt = select(Event)
        if lead_id is not None:
            stmt = stmt.where(Event.lead_id == lead_id)
        if level is not None:
            stmt = stmt.where(Event.level == level)
        stmt = stmt.order_by(Event.ts.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class LlmCallRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, call: LlmCall) -> LlmCall:
        self.session.add(call)
        self.session.flush()
        return call

    def spend_today_usd(self, *, now: datetime | None = None) -> Decimal:
        start = _start_of_local_day(now or utcnow())
        stmt = select(LlmCall.cost_usd).where(LlmCall.ts >= start)
        total = Decimal("0")
        for cost in self.session.scalars(stmt):
            total += Decimal(cost)
        return total


class JobRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, run_id: str) -> JobRun | None:
        return self.session.get(JobRun, run_id)

    def start(self, job: str) -> JobRun:
        row = JobRun(job=job, status="running", processed=0, started_at=utcnow())
        self.session.add(row)
        self.session.flush()
        return row

    def finish(
        self,
        run: JobRun,
        *,
        status: str,
        processed: int,
        error: str | None = None,
    ) -> JobRun:
        self.session.execute(
            update(JobRun)
            .where(JobRun.id == run.id)
            .values(
                status=status,
                processed=processed,
                error=error,
                finished_at=utcnow(),
            )
        )
        self.session.flush()
        self.session.refresh(run)
        return run

    def list(self, *, job: str | None = None, limit: int = 100) -> list[JobRun]:
        stmt = select(JobRun)
        if job is not None:
            stmt = stmt.where(JobRun.job == job)
        stmt = stmt.order_by(JobRun.started_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class DataRequestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, request_id: str) -> DataRequest | None:
        return self.session.get(DataRequest, request_id)

    def add(
        self,
        *,
        kind: str,
        requester_email: str,
        details: str | None = None,
        status: str = "open",
        due_at: datetime | None = None,
    ) -> DataRequest:
        row = DataRequest(
            kind=kind,
            requester_email=requester_email,
            details=details,
            status=status,
            due_at=due_at or (utcnow() + timedelta(days=_DATA_REQUEST_DAYS)),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list(self, *, status: str | None = None, limit: int = 100) -> list[DataRequest]:
        stmt = select(DataRequest)
        if status is not None:
            stmt = stmt.where(DataRequest.status == status)
        stmt = stmt.order_by(DataRequest.due_at.asc()).limit(limit)
        return list(self.session.scalars(stmt).all())
