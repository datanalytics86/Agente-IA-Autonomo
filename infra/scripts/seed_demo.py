"""Siembra una landing demo en disco para el smoke. No publica ni cobra."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from db.models import Artifact, Lead
from db.session import session_scope

TOKEN = "smoke-demo-token"
RELATIVE = "output/demo/smoke-demo.html"
HTML = (
    '<!doctype html><html lang="es"><head><meta charset="utf-8">'
    "<title>Demo de prueba</title></head><body>"
    "<p>Demo sembrada para el smoke. No es una publicación real.</p>"
    "</body></html>\n"
)


def main() -> int:
    path = Path("/app") / RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HTML, encoding="utf-8")
    with session_scope() as session:
        artifact = session.scalar(select(Artifact).where(Artifact.public_token == TOKEN))
        if artifact is None:
            lead = Lead(
                source="smoke",
                business="Demo smoke",
                category="cafeteria",
                city="Santiago",
                commune="Ñuñoa",
                opportunity_score=10,
                status="diagnosticado",
                estimated_value_clp=0,
                high_value=False,
                tone="tu",
            )
            session.add(lead)
            session.flush()
            session.add(
                Artifact(
                    lead_id=lead.id,
                    kind="landing_demo",
                    path=RELATIVE,
                    public_token=TOKEN,
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                )
            )
        else:
            artifact.path = RELATIVE
            artifact.expires_at = datetime.now(UTC) + timedelta(days=7)
            session.add(artifact)
    print(f"TOKEN={TOKEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
