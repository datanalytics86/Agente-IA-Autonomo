"""Dicts de salida. No asigna estados."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from db.models import Artifact, Event, Lead, LeadEvent, Message, Order, Project


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def lead_dict(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "business": lead.business,
        "category": lead.category,
        "city": lead.city,
        "commune": lead.commune,
        "status": lead.status,
        "source": lead.source,
        "estimated_value_clp": lead.estimated_value_clp,
        "high_value": lead.high_value,
        "opportunity_score": lead.opportunity_score,
        "paused_from": lead.paused_from,
    }


def message_dict(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "lead_id": message.lead_id,
        "channel": message.channel,
        "direction": message.direction,
        "status": message.status,
        "subject": message.subject,
        "body_text": message.body_text,
        "check_result": message.check_result,
    }


def event_dict(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "ts": event.ts.isoformat(),
        "agent": event.agent,
        "level": event.level,
        "message": event.message,
        "lead_id": event.lead_id,
    }


def timeline_dict(event: LeadEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "actor": event.actor,
        "reason": event.reason,
        "ts": event.ts.isoformat(),
    }


def artifact_dict(artifact: Artifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "kind": artifact.kind,
        "version": artifact.version,
        "public_token": artifact.public_token,
        "expires_at": iso(artifact.expires_at),
    }


def order_dict(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "lead_id": order.lead_id,
        "package_code": order.package_code,
        "status": order.status,
        "total_clp": order.total_clp,
    }


def project_dict(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "status": project.status,
        "revisions_used": project.revisions_used,
        "max_revisions": project.max_revisions,
        "domain": project.domain,
        "deploy_url": project.deploy_url,
    }
