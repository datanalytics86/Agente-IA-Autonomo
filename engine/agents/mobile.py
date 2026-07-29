"""Mobile — respuestas cortas + link Calendly para leads calientes."""

from __future__ import annotations

import os
from typing import Optional

from agents.base import (
    Lead,
    LeadStatus,
    leads_by_status,
    log_event,
    read_prompt,
    upsert_lead,
)


def calendly_link() -> str:
    return os.getenv(
        "CALENDLY_LINK",
        "https://calendly.com/demo-agente-ia/diagnostico",
    )


def reply_templates(lead: Lead) -> dict[str, str]:
    _ = read_prompt("mobile")
    link = calendly_link()
    name = lead.business
    return {
        "interesado": (
            f"Bacán que te interese. Te dejo el link para agendar 15 min sin compromiso: {link}\n"
            f"Si prefieres, me dices un horario esta semana y lo coordinamos. — Sobre {name}"
        ),
        "pregunta_precio": (
            f"El paquete landing para pymes locales va entre $250.000 y $450.000 CLP "
            f"(según alcance). Pagos: transferencia, Mercado Pago o Webpay. "
            f"¿Agendamos una llamada corta? {link}"
        ),
        "objeccion_tiempo": (
            "Entiendo el ajetreo. La llamada es de 15 minutos y te llevas un diagnóstico claro, "
            f"aunque no sigamos. Cuando te acomode: {link}"
        ),
        "no_interesado": (
            "Perfecto, gracias por avisar. No te escribo más sobre esto. "
            "Si más adelante te sirve, aquí estaré. Éxito con el negocio."
        ),
        "agendar": (
            f"Listo. Reserva aquí y te llega la confirmación: {link}\n"
            "Cualquier duda antes de la llamada, escríbeme por este mismo canal."
        ),
    }


def handle_hot_lead(lead: Lead, intent: str = "interesado") -> Lead:
    """Procesa lead en ENVIADO/RESPONDIO: prepara respuesta y puede agendar."""
    templates = reply_templates(lead)
    reply = templates.get(intent, templates["interesado"])

    if lead.send_simulation is None:
        lead.send_simulation = {}
    lead.send_simulation["mobile_reply"] = {
        "intent": intent,
        "reply": reply,
        "calendly": calendly_link(),
    }

    if intent in ("interesado", "agendar", "pregunta_precio"):
        if lead.status in (LeadStatus.ENVIADO, LeadStatus.RESPONDIO):
            if intent == "agendar":
                lead.status = LeadStatus.AGENDADO
            else:
                lead.status = LeadStatus.RESPONDIO
    elif intent == "no_interesado":
        lead.status = LeadStatus.CERRADO
        lead.reason = (lead.reason or "") + " | Lead no interesado (opt-out respetado)"

    upsert_lead(lead)
    log_event(
        "Mobile",
        f"respuesta · {lead.business} · intent={intent} → {lead.status.value}",
        meta={"lead_id": lead.id, "intent": intent},
    )
    return lead


def run_mobile(
    leads: Optional[list[Lead]] = None,
    simulate_interest: bool = False,
) -> list[Lead]:
    """
    En demo, opcionalmente simula que un lead enviado respondió con interés.
    """
    targets = leads if leads is not None else (
        leads_by_status(LeadStatus.ENVIADO) + leads_by_status(LeadStatus.RESPONDIO)
    )
    out: list[Lead] = []
    if not simulate_interest:
        # Solo prepara templates en log si hay enviados
        for lead in targets:
            if lead.status == LeadStatus.ENVIADO:
                t = reply_templates(lead)
                log_event(
                    "Mobile",
                    f"plantillas listas · {lead.business} (esperando respuesta real)",
                    meta={"lead_id": lead.id, "sample": t["interesado"][:120]},
                )
        return out

    for lead in targets:
        if lead.status == LeadStatus.ENVIADO:
            out.append(handle_hot_lead(lead, intent="interesado"))
            # En demo, el primero interesado se agenda
            if out and len(out) == 1:
                out[-1] = handle_hot_lead(out[-1], intent="agendar")
            break

    log_event("Mobile", f"{len(out)} leads calientes procesados")
    return out
