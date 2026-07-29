"""Scout — encuentra o genera leads locales (demo: sintéticos realistas Chile)."""

from __future__ import annotations

import random
from typing import Optional

from agents.base import (
    HIGH_VALUE_CLP,
    Lead,
    LeadStatus,
    log_event,
    read_prompt,
    upsert_leads,
)

# Ciudades/comunas piloto Chile
PILOT_LOCATIONS = [
    ("Santiago", "Providencia"),
    ("Santiago", "Las Condes"),
    ("Santiago", "Ñuñoa"),
    ("Santiago", "Maipú"),
    ("Viña del Mar", "Viña del Mar"),
    ("Valparaíso", "Valparaíso"),
    ("Concepción", "Concepción"),
    ("Temuco", "Temuco"),
    ("La Serena", "La Serena"),
]

CATEGORIES = [
    ("Clínica dental", "salud"),
    ("Peluquería", "belleza"),
    ("Cafetería", "gastronomía"),
    ("Taller mecánico", "automotriz"),
    ("Estudio contable", "servicios profesionales"),
    ("Gimnasio boutique", "fitness"),
    ("Inmobiliaria local", "inmobiliaria"),
    ("Veterinaria", "mascotas"),
    ("Estudio de abogados", "legal"),
    ("Centro de estética", "belleza"),
    ("Restaurante de barrio", "gastronomía"),
    ("Óptica", "salud"),
    ("Escuela de idiomas", "educación"),
    ("Ferretería", "retail"),
    ("Spa y masajes", "bienestar"),
]

BUSINESS_PREFIXES = [
    "Clínica", "Centro", "Espacio", "Studio", "Casa", "Taller",
    "Oficina", "Grupo", "Red", "Punto", "Nodo", "Huella",
]

BUSINESS_SUFFIXES = [
    "Andes", "Pacifico", "del Sur", "Mapocho", "Cordillera",
    "Maipo", "Bío Bío", "Araucanía", "Costanera", "Barrio",
    "Local", "Express", "Pro", "Plus", "Chile",
]

NAMES_CHILE = [
    "San Martín", "Los Aromos", "Santa Lucía", "El Roble",
    "Las Palmas", "Los Leones", "Providencia", "Norte",
]


def _synthetic_name(category_label: str) -> str:
    style = random.choice(["compound", "person", "place"])
    if style == "compound":
        return f"{random.choice(BUSINESS_PREFIXES)} {random.choice(BUSINESS_SUFFIXES)}"
    if style == "person":
        return f"{category_label} {random.choice(NAMES_CHILE)}"
    return f"{random.choice(NAMES_CHILE)} {category_label}"


def generate_demo_leads(n: int = 3, force_high_value: bool = True) -> list[Lead]:
    """Genera n leads chilenos realistas. Uno puede ser high-value para demo HITL."""
    _ = read_prompt("scout")  # carga prompt (extensible a LLM)
    leads: list[Lead] = []
    used: set[str] = set()

    for i in range(n):
        city, commune = random.choice(PILOT_LOCATIONS)
        cat_label, cat_slug = random.choice(CATEGORIES)
        name = _synthetic_name(cat_label)
        while name in used:
            name = _synthetic_name(cat_label)
        used.add(name)

        has_web = random.random() < 0.35
        website_year = random.randint(2014, 2021) if has_web else None
        rating = round(random.uniform(3.6, 4.9), 1)
        reviews = random.randint(8, 280)

        # Paquete estándar 250k–450k; uno high-value en demo
        if force_high_value and i == 0:
            value = random.randint(2_900_000, 3_800_000)
            reason = (
                "Lead demo high-value: paquete multi-sede / red local "
                f"sin presencia web moderna en {commune}."
            )
        else:
            value = random.randint(250_000, 450_000)
            if not has_web:
                reason = f"Sin sitio web visible; oportunidad en {commune} ({cat_label})."
            else:
                reason = (
                    f"Sitio desactualizado (~{website_year}); "
                    f"buena reputación ({rating}★ / {reviews} reseñas) sin conversión online."
                )

        lead = Lead(
            business=name,
            category=cat_slug,
            city=city,
            commune=commune,
            has_website=has_web,
            website_year=website_year,
            rating=rating,
            reviews=reviews,
            status=LeadStatus.NUEVO,
            estimated_value_clp=value,
            reason=reason,
            channels=["instagram_dm", "email", "linkedin"],
            contact_hint=f"Búsqueda pública: {name} · {commune} · Instagram/Google Maps",
            high_value=value >= HIGH_VALUE_CLP,
        )
        leads.append(lead)

    return leads


def run_scout(count: int = 3, force_high_value: bool = True) -> list[Lead]:
    """Ejecuta Scout en modo demo y persiste leads."""
    leads = generate_demo_leads(n=count, force_high_value=force_high_value)
    upsert_leads(leads)

    communes = sorted({l.commune for l in leads})
    commune_str = ", ".join(communes)
    log_event(
        "Scout",
        f"{len(leads)} leads nuevos en {commune_str}",
        meta={"ids": [l.id for l in leads], "count": len(leads)},
    )
    return leads
