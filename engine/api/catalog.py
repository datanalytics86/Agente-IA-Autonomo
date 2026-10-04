"""Paquetes y rubros del contrato. Los precios pueden taparse en settings_kv."""

from __future__ import annotations

from typing import Any

CATEGORIES: tuple[tuple[str, str, str, str], ...] = (
    ("clinica-dental", "Clínica dental", "formal", "usted"),
    ("optica", "Óptica", "formal", "usted"),
    ("abogados", "Estudio de abogados", "formal", "usted"),
    ("estudio-contable", "Estudio contable", "formal", "usted"),
    ("peluqueria", "Peluquería", "belleza", "tu"),
    ("centro-estetica", "Centro de estética", "belleza", "tu"),
    ("spa", "Spa y masajes", "belleza", "tu"),
    ("gimnasio", "Gimnasio boutique", "belleza", "tu"),
    ("cafeteria", "Cafetería", "gastronomia", "tu"),
    ("restaurante", "Restaurante de barrio", "gastronomia", "tu"),
    ("taller-mecanico", "Taller mecánico", "servicios", "tu"),
    ("inmobiliaria", "Inmobiliaria local", "servicios", "tu"),
    ("veterinaria", "Veterinaria", "servicios", "tu"),
    ("escuela-idiomas", "Escuela de idiomas", "servicios", "tu"),
    ("ferreteria", "Ferretería", "servicios", "tu"),
)

CATEGORY_SLUGS = frozenset(item[0] for item in CATEGORIES)
HIGH_VALUE_CATEGORIES = frozenset({"clinica-dental", "optica", "inmobiliaria", "abogados"})

PACKAGES: tuple[dict[str, Any], ...] = (
    {
        "code": "landing_esencial",
        "name": "Landing esencial",
        "price_clp": 250_000,
        "revisions": 1,
        "includes": ("5 secciones", "publicación"),
    },
    {
        "code": "landing_pro",
        "name": "Landing pro",
        "price_clp": 350_000,
        "revisions": 2,
        "includes": ("esencial", "video 12 s", "formulario", "WhatsApp del cliente"),
    },
    {
        "code": "landing_premium",
        "name": "Landing premium",
        "price_clp": 450_000,
        "revisions": 3,
        "includes": ("pro", "SEO local", "schema.org"),
    },
    {
        "code": "multi_sede",
        "name": "Multi sede",
        "price_clp": None,
        "revisions": 0,
        "includes": ("a cotizar", "siempre revisión humana"),
    },
)


def tone_for(category: str) -> str:
    for slug, _label, _theme, tone in CATEGORIES:
        if slug == category:
            return str(tone)
    return "tu"


def revisions_for(code: str) -> int:
    for item in PACKAGES:
        if item["code"] == code:
            return int(item["revisions"])
    return 1


def split_iva(price: int, includes_iva: bool) -> tuple[int, int, int]:
    if includes_iva:
        net = int(round(price / 1.19))
        iva = price - net
        return net, iva, price
    iva = int(round(price * 0.19))
    return price, iva, price + iva
