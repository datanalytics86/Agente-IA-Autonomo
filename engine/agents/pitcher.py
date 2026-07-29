"""Pitcher — prepara y simula envíos por canales permitidos (nunca sin Checker)."""

from __future__ import annotations

from typing import Any, Optional

from agents.base import (
    Lead,
    LeadStatus,
    leads_by_status,
    log_event,
    read_prompt,
    upsert_lead,
    utc_now_iso,
)


ALLOWED_CHANNELS = ("instagram_dm", "email", "linkedin")
CAUTION_CHANNELS = ("whatsapp",)


def _simulate_send(lead: Lead, channel: str) -> dict[str, Any]:
    return {
        "channel": channel,
        "status": "simulated",
        "to_hint": lead.contact_hint or f"{lead.business} · canal público",
        "subject": f"Presencia web para {lead.business} en {lead.commune}",
        "body_preview": (lead.pitch or "")[:280],
        "ts": utc_now_iso(),
        "note": "Simulación demo — no se envió mensaje real.",
    }


def pitch_lead(lead: Lead, include_whatsapp_warning: bool = True) -> Lead:
    _ = read_prompt("pitcher")

    # NUNCA enviar sin Checker aprobado
    check = lead.check_result or {}
    if not check.get("approved"):
        log_event(
            "Pitcher",
            f"bloqueo · {lead.business} sin aprobación de Checker",
            level="error",
            meta={"lead_id": lead.id},
        )
        lead.send_simulation = {
            "blocked": True,
            "reason": "Checker no aprobó el pitch",
            "ts": utc_now_iso(),
        }
        upsert_lead(lead)
        return lead

    if lead.status == LeadStatus.REVISION:
        log_event(
            "Pitcher",
            f"omitido · {lead.business} en revisión humana (HITL)",
            level="warn",
            meta={"lead_id": lead.id},
        )
        lead.send_simulation = {
            "blocked": True,
            "reason": "Lead en status revision (human-in-the-loop)",
            "ts": utc_now_iso(),
        }
        upsert_lead(lead)
        return lead

    sends = [_simulate_send(lead, ch) for ch in ALLOWED_CHANNELS]
    caution: list[dict[str, Any]] = []
    if include_whatsapp_warning:
        caution.append(
            {
                "channel": "whatsapp",
                "status": "not_sent",
                "warning": (
                    "WhatsApp NO se usa en cold outreach agresivo. "
                    "Solo post-engagement o con consentimiento. Simulación bloqueada."
                ),
                "ts": utc_now_iso(),
            }
        )

    lead.send_simulation = {
        "blocked": False,
        "sends": sends,
        "caution": caution,
        "ts": utc_now_iso(),
    }
    lead.status = LeadStatus.ENVIADO
    upsert_lead(lead)

    channels = ", ".join(ALLOWED_CHANNELS)
    log_event(
        "Pitcher",
        f"envío simulado · {lead.business} · {channels} (WhatsApp: solo warning)",
        meta={"lead_id": lead.id, "channels": list(ALLOWED_CHANNELS)},
    )
    return lead


def run_pitcher(leads: Optional[list[Lead]] = None) -> list[Lead]:
    targets = leads if leads is not None else leads_by_status(LeadStatus.PITCH_LISTO)
    out: list[Lead] = []
    for lead in targets:
        if lead.status != LeadStatus.PITCH_LISTO:
            continue
        out.append(pitch_lead(lead))
    log_event("Pitcher", f"{len(out)} envíos simulados")
    return out
