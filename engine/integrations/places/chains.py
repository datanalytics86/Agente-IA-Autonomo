"""Cadenas y franquicias que el scout no prospecta."""

from __future__ import annotations

import re

from db.normalize import normalize_business

# Frases completas, no tokens sueltos como "paris" o "easy".
_CHAINS: tuple[str, ...] = (
    "starbucks",
    "mcdonald",
    "mcdonalds",
    "burger king",
    "kfc",
    "jumbo",
    "lider",
    "santa isabel",
    "falabella",
    "ripley",
    "cruz verde",
    "salcobrand",
    "farmacias ahumada",
    "ahumada",
    "dr simi",
    "doctor simi",
    "integramedica",
    "megasalud",
    "clinica santa maria",
    "unimarc",
    "tottus",
    "sodimac",
    "homecenter",
    "subway",
    "domino",
    "pizza hut",
    "dunkin",
    "papa johns",
)


def is_chain(name: str) -> bool:
    normalized = normalize_business(name)
    for chain in _CHAINS:
        if re.search(rf"(^| ){re.escape(chain)}( |$)", normalized):
            return True
    return False
