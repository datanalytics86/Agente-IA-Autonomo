"""LeadSource: DemoSource estable y Google Places (Places API New)."""

from __future__ import annotations

import random
import re
import unicodedata
from typing import Protocol

import httpx
from pydantic import BaseModel, Field

from agents.catalog import CATEGORY_LABELS, CATEGORY_SLUGS
from core.config import Settings, get_settings
from integrations.places.chains import is_chain

_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = ",".join(
    (
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.types",
        "places.googleMapsUri",
        "places.nationalPhoneNumber",
    )
)

_NAMES: dict[str, tuple[str, ...]] = {
    "clinica-dental": (
        "Clínica Dental Los Aromos",
        "Clínica Dental El Roble",
        "Clínica Dental Santa Lucía",
    ),
    "optica": ("Óptica Cordillera", "Óptica Los Leones", "Óptica Del Sur"),
    "abogados": (
        "Estudio Jurídico Mapocho",
        "Abogados del Barrio",
        "Estudio Legal Costanera",
    ),
    "estudio-contable": (
        "Estudio Contable Maipo",
        "Contadores del Sur",
        "Estudio Contable Pacífico",
    ),
    "peluqueria": (
        "Peluquería Las Palmas",
        "Peluquería El Roble",
        "Peluquería Barrio Norte",
    ),
    "centro-estetica": (
        "Centro de Estética Los Aromos",
        "Estética Santa Lucía",
        "Centro Estético Cordillera",
    ),
    "spa": ("Spa Los Leones", "Spa del Barrio", "Spa Costanera"),
    "gimnasio": (
        "Gimnasio Boutique El Roble",
        "Gimnasio Los Aromos",
        "Gimnasio del Barrio",
    ),
    "cafeteria": (
        "Cafetería Las Palmas",
        "Cafetería Mapocho",
        "Café de Barrio Los Aromos",
    ),
    "restaurante": (
        "Restaurante El Roble",
        "Restaurante del Barrio",
        "Cocina Local Costanera",
    ),
    "taller-mecanico": (
        "Taller Mecánico Los Aromos",
        "Taller El Roble",
        "Taller del Barrio",
    ),
    "inmobiliaria": (
        "Inmobiliaria Los Leones",
        "Inmobiliaria del Barrio",
        "Propiedades Cordillera",
    ),
    "veterinaria": (
        "Veterinaria Las Palmas",
        "Veterinaria El Roble",
        "Veterinaria del Barrio",
    ),
    "escuela-idiomas": (
        "Escuela de Idiomas Mapocho",
        "Idiomas del Barrio",
        "Escuela Costanera",
    ),
    "ferreteria": (
        "Ferretería Los Aromos",
        "Ferretería El Roble",
        "Ferretería del Barrio",
    ),
}


class PlaceHit(BaseModel):
    place_id: str
    name: str
    formatted_address: str
    website_uri: str | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    business_status: str
    types: list[str] = Field(default_factory=list)
    google_maps_uri: str | None = None
    national_phone_number: str | None = None


class LeadSource(Protocol):
    def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]: ...


def _slug(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = plain.lower().replace("ñ", "n")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or "negocio"


def accepts(hit: PlaceHit, *, min_rating: float, min_reviews: int) -> bool:
    if hit.business_status != "OPERATIONAL":
        return False
    if hit.rating is None or hit.rating < min_rating:
        return False
    if hit.user_rating_count is None or hit.user_rating_count < min_reviews:
        return False
    return not is_chain(hit.name)


class DemoSource:
    """Generador estable. No abre sockets ni inventa correos."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]:
        names = _NAMES.get(category_slug) or _NAMES["ferreteria"]
        rng = random.Random(f"{self.seed}:{commune}:{category_slug}")
        ordered = list(names)
        rng.shuffle(ordered)
        hits: list[PlaceHit] = []
        for name in ordered[: max(0, limit)]:
            rating = round(4.2 + rng.randint(0, 6) / 10, 1)
            reviews = rng.randint(18, 90)
            website = None
            if rng.random() >= 0.6:
                website = f"https://demo.invalid/{_slug(name)}"
            hits.append(
                PlaceHit(
                    place_id=f"demo-{_slug(name)}-{_slug(commune)}",
                    name=name,
                    formatted_address=f"{commune}, Chile",
                    website_uri=website,
                    rating=rating,
                    user_rating_count=reviews,
                    business_status="OPERATIONAL",
                    types=[category_slug],
                    google_maps_uri=None,
                    national_phone_number=None,
                )
            )
        return hits


class GooglePlacesSource:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        min_rating: float = 4.0,
        min_reviews: int = 15,
    ) -> None:
        self.api_key = api_key
        self.min_rating = min_rating
        self.min_reviews = min_reviews
        self._client = client
        self._owns = client is None

    def search(self, commune: str, category_slug: str, limit: int) -> list[PlaceHit]:
        label = CATEGORY_LABELS.get(category_slug, category_slug)
        client = self._client or httpx.Client(timeout=15.0)
        try:
            response = client.post(
                _PLACES_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": _FIELD_MASK,
                },
                json={
                    "textQuery": f"{label} en {commune}, Chile",
                    "pageSize": max(limit, 1),
                    "languageCode": "es",
                    "regionCode": "CL",
                },
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if self._owns:
                client.close()
        hits: list[PlaceHit] = []
        for raw in payload.get("places") or []:
            hit = _parse_place(raw)
            if hit is None:
                continue
            if not accepts(hit, min_rating=self.min_rating, min_reviews=self.min_reviews):
                continue
            hits.append(hit)
            if len(hits) >= limit:
                break
        return hits


def _parse_place(raw: object) -> PlaceHit | None:
    if not isinstance(raw, dict):
        return None
    place_id = raw.get("id")
    display = raw.get("displayName") or {}
    name = display.get("text") if isinstance(display, dict) else None
    if not isinstance(place_id, str) or not isinstance(name, str) or not name.strip():
        return None
    raw_types = raw.get("types")
    types = raw_types if isinstance(raw_types, list) else []
    return PlaceHit(
        place_id=place_id,
        name=name.strip(),
        formatted_address=str(raw.get("formattedAddress") or ""),
        website_uri=raw.get("websiteUri") if isinstance(raw.get("websiteUri"), str) else None,
        rating=float(raw["rating"]) if isinstance(raw.get("rating"), (int, float)) else None,
        user_rating_count=(
            int(raw["userRatingCount"]) if isinstance(raw.get("userRatingCount"), int) else None
        ),
        business_status=str(raw.get("businessStatus") or ""),
        types=[str(item) for item in types],
        google_maps_uri=(
            raw.get("googleMapsUri") if isinstance(raw.get("googleMapsUri"), str) else None
        ),
        national_phone_number=(
            raw.get("nationalPhoneNumber")
            if isinstance(raw.get("nationalPhoneNumber"), str)
            else None
        ),
    )


def build_places(settings: Settings | None = None) -> LeadSource:
    current = settings or get_settings()
    if not current.google_places_api_key or current.dry_run or current.app_mode == "demo":
        return DemoSource()
    return GooglePlacesSource(
        current.google_places_api_key,
        min_rating=current.scout_min_rating,
        min_reviews=current.scout_min_reviews,
    )


def known_category(slug: str) -> bool:
    return slug in CATEGORY_SLUGS
