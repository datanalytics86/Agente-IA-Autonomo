"""Rubros, temas y paquetes. La tabla canónica está en el contrato de dominio."""

from __future__ import annotations

CATEGORY_SLUGS: tuple[str, ...] = (
    "clinica-dental",
    "optica",
    "abogados",
    "estudio-contable",
    "peluqueria",
    "centro-estetica",
    "spa",
    "gimnasio",
    "cafeteria",
    "restaurante",
    "taller-mecanico",
    "inmobiliaria",
    "veterinaria",
    "escuela-idiomas",
    "ferreteria",
)

CATEGORY_LABELS: dict[str, str] = {
    "clinica-dental": "Clínica dental",
    "optica": "Óptica",
    "abogados": "Estudio de abogados",
    "estudio-contable": "Estudio contable",
    "peluqueria": "Peluquería",
    "centro-estetica": "Centro de estética",
    "spa": "Spa y masajes",
    "gimnasio": "Gimnasio boutique",
    "cafeteria": "Cafetería",
    "restaurante": "Restaurante de barrio",
    "taller-mecanico": "Taller mecánico",
    "inmobiliaria": "Inmobiliaria local",
    "veterinaria": "Veterinaria",
    "escuela-idiomas": "Escuela de idiomas",
    "ferreteria": "Ferretería",
}

THEME_BY_CATEGORY: dict[str, str] = {
    "clinica-dental": "formal",
    "optica": "formal",
    "abogados": "formal",
    "estudio-contable": "formal",
    "peluqueria": "belleza",
    "centro-estetica": "belleza",
    "spa": "belleza",
    "gimnasio": "belleza",
    "cafeteria": "gastronomia",
    "restaurante": "gastronomia",
    "taller-mecanico": "servicios",
    "inmobiliaria": "servicios",
    "veterinaria": "servicios",
    "escuela-idiomas": "servicios",
    "ferreteria": "servicios",
}

TONE_BY_CATEGORY: dict[str, str] = {
    "clinica-dental": "usted",
    "optica": "usted",
    "abogados": "usted",
    "estudio-contable": "usted",
    "peluqueria": "tu",
    "centro-estetica": "tu",
    "spa": "tu",
    "gimnasio": "tu",
    "cafeteria": "tu",
    "restaurante": "tu",
    "taller-mecanico": "tu",
    "inmobiliaria": "tu",
    "veterinaria": "tu",
    "escuela-idiomas": "tu",
    "ferreteria": "tu",
}

# Alto valor forzado solo en demo y solo en estos rubros.
DEMO_HIGH_VALUE_CATEGORIES: frozenset[str] = frozenset(
    {"clinica-dental", "optica", "inmobiliaria", "abogados"}
)

THEMES: tuple[str, ...] = ("formal", "belleza", "gastronomia", "servicios")

PACKAGE_CLP: dict[str, int | None] = {
    "landing_esencial": 250_000,
    "landing_pro": 350_000,
    "landing_premium": 450_000,
    "multi_sede": None,
}

COMMUNE_CITY: dict[str, str] = {
    "Providencia": "Santiago",
    "Las Condes": "Santiago",
    "Ñuñoa": "Santiago",
    "Maipú": "Santiago",
    "Viña del Mar": "Viña del Mar",
    "Valparaíso": "Valparaíso",
    "Concepción": "Concepción",
    "Temuco": "Temuco",
    "La Serena": "La Serena",
}

SAFE_INTENTS: frozenset[str] = frozenset(
    {"interesado", "pregunta_precio", "pregunta_detalle", "objecion_tiempo", "agendar"}
)
