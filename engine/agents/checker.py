"""Checker — calidad + compliance Ley 21.719 + anti-spam."""

from __future__ import annotations

import re
from typing import Any, Optional

from agents.base import (
    Lead,
    LeadStatus,
    leads_by_status,
    log_event,
    read_prompt,
    upsert_lead,
)

# Patrones que sugieren datos inventados o spam agresivo
PHONE_RE = re.compile(
    r"(?:\+?56\s*)?(?:9\s*)?\d{4}[\s\-]?\d{4}|\b\d{8,9}\b"
)
EMAIL_INVENTED_RE = re.compile(
    r"\b[\w.+-]+@(?:gmail|hotmail|yahoo|outlook)\.com\b", re.I
)
BANNED_PHRASES = [
    "garantizado 100%",
    "hazte rico",
    "solo hoy",
    "última oportunidad!!!",
    "sin esfuerzo",
    "te voy a spamear",
]


def _has_opt_out(text: str) -> bool:
    t = text.lower()
    return any(
        k in t
        for k in ("stop", "no vuelvo a escribir", "darse de baja", "opt-out", "no deseo")
    )


def check_lead(lead: Lead) -> Lead:
    _ = read_prompt("checker")
    issues: list[str] = []
    warnings: list[str] = []
    score = 100

    pitch = lead.pitch or ""
    diagnosis = lead.diagnosis or ""
    combined = f"{pitch}\n{diagnosis}"

    if not pitch.strip():
        issues.append("Falta pitch de prospección")
        score -= 40
    if not diagnosis.strip():
        issues.append("Falta diagnóstico")
        score -= 20
    if not lead.landing_path:
        warnings.append("Sin landing generada aún")
        score -= 10

    if pitch and not _has_opt_out(pitch):
        issues.append("Pitch sin opt-out claro (STOP / no volver a escribir)")
        score -= 25

    # No inventar teléfonos: si el pitch incluye números que parecen celulares chilenos inventados
    phones = PHONE_RE.findall(pitch)
    if phones:
        warnings.append(
            f"Pitch contiene posibles teléfonos ({phones[:2]}). "
            "Solo usar si son públicos verificados."
        )
        score -= 5

    emails = EMAIL_INVENTED_RE.findall(pitch)
    if emails:
        warnings.append(
            "Posibles emails genéricos en el pitch; no inventar contactos no públicos."
        )
        score -= 10

    for phrase in BANNED_PHRASES:
        if phrase in combined.lower():
            issues.append(f"Lenguaje no permitido / spam: “{phrase}”")
            score -= 15

    # WhatsApp cold
    if "whatsapp" in pitch.lower() and "solo si" not in pitch.lower():
        if any(w in pitch.lower() for w in ("escríbeme al whatsapp", "te escribo al whats")):
            issues.append("WhatsApp cold agresivo no permitido")
            score -= 20
        else:
            warnings.append("Mención a WhatsApp: preferir post-engagement")

    # Ley 21.719 — minimización y finalidad
    ley_ok = (
        "21.719" in combined
        or "datos personales" in combined.lower()
        or _has_opt_out(pitch)
    )
    if not ley_ok:
        warnings.append("Reforzar mención de privacidad / opt-out (Ley 21.719)")
        score -= 5

    score = max(0, min(100, score))
    approved = score >= 70 and not issues

    result: dict[str, Any] = {
        "approved": approved,
        "score": score,
        "issues": issues,
        "warnings": warnings,
        "ley_21719": {
            "opt_out": _has_opt_out(pitch),
            "no_invented_private_contact": len(emails) == 0,
            "notes": "Prospección B2B con datos públicos; opt-out obligatorio.",
        },
        "channels_allowed": ["instagram_dm", "email", "linkedin"],
        "channels_caution": ["whatsapp"],
    }
    lead.check_result = result

    if lead.status == LeadStatus.REVISION:
        # No avanzar automatico high-value
        pass
    elif approved and lead.status == LeadStatus.VIDEO:
        lead.status = LeadStatus.PITCH_LISTO
    elif not approved and lead.status == LeadStatus.VIDEO:
        lead.status = LeadStatus.REVISION
        lead.reason = (lead.reason or "") + " | Checker rechazó pitch: " + "; ".join(issues)

    upsert_lead(lead)

    if approved:
        log_event(
            "Checker",
            f"pitch aprobado · opt-out OK · {lead.business} (score {score})",
            meta={"lead_id": lead.id, "score": score},
        )
    else:
        log_event(
            "Checker",
            f"pitch RECHAZADO · {lead.business}: {'; '.join(issues) or 'score bajo'}",
            level="warn",
            meta={"lead_id": lead.id, "score": score, "issues": issues},
        )
    return lead


def run_checker(leads: Optional[list[Lead]] = None) -> list[Lead]:
    targets = leads if leads is not None else leads_by_status(LeadStatus.VIDEO)
    out: list[Lead] = []
    for lead in targets:
        if lead.status in (LeadStatus.VIDEO, LeadStatus.REVISION) and lead.pitch:
            # Para REVISION high-value igual corremos check (auditoría)
            if lead.status == LeadStatus.REVISION and not lead.video_path and not lead.landing_path:
                continue
            out.append(check_lead(lead))
    log_event("Checker", f"{len(out)} pitches revisados")
    return out
