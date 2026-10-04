"""Repositorios, lock de SQLite, seed y alembic upgrade head."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import reset_settings
from core.errors import DuplicateLeadError
from db.models import Base, Lead, LlmCall, Message, Order, Payment, Setting
from db.repositories import (
    DataRequestRepository,
    JobRunRepository,
    LeadRepository,
    LlmCallRepository,
    MessageRepository,
    PaymentRepository,
    SettingsRepository,
    SuppressionRepository,
    due_messages_statement,
)
from db.seed import main as seed_main
from db.session import create_all, get_engine, reset_engine, session_scope

ENGINE = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _caches() -> object:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    url = f"sqlite:///{(tmp_path / 'repo.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_settings()
    reset_engine()
    create_all()
    with session_scope() as current:
        yield current


def make_lead(**overrides: Any) -> Lead:
    data: dict[str, Any] = {
        "source": "outbound_demo",
        "business": "Café Andes",
        "category": "cafeteria",
        "city": "Santiago",
        "commune": "Providencia",
        "opportunity_score": 70,
        "status": "nuevo",
        "estimated_value_clp": 250_000,
        "high_value": False,
        "tone": "tu",
    }
    data.update(overrides)
    return Lead(**data)


def test_lead_crud_y_nombre_normalizado(session: Session) -> None:
    repo = LeadRepository(session)
    lead = repo.add(make_lead(business="Café Ñuñoa"))
    assert repo.get(lead.id) is not None
    assert repo.list(status="nuevo")[0].id == lead.id
    lead.city = "Valparaíso"
    repo.save(lead)
    stored = repo.get(lead.id)
    assert stored is not None
    assert stored.city == "Valparaíso"

    with pytest.raises(DuplicateLeadError):
        repo.add(make_lead(business="Cafe Nunoa"))
    anon = repo.add(
        make_lead(
            business="Café Ñuñoa",
            commune="Providencia",
            anonymized_at=datetime.now(UTC),
        )
    )
    assert anon.anonymized_at is not None
    other_commune = repo.add(make_lead(business="Café Ñuñoa", commune="Maipú"))
    assert other_commune.commune == "Maipú"


def test_place_id_unico(session: Session) -> None:
    repo = LeadRepository(session)
    repo.add(make_lead(place_id="places/1", business="Uno"))
    with pytest.raises(IntegrityError):
        repo.add(make_lead(place_id="places/1", business="Dos"))
    session.rollback()


def test_supresion_guarda_solo_el_hash(session: Session) -> None:
    repo = SuppressionRepository(session)
    assert repo.contains("email", "A@B.cl") is False
    row = repo.add("email", "A@B.cl", reason="baja", source="test")
    assert repo.contains("email", "a@b.cl") is True
    again = repo.add("email", "a@b.cl", reason="baja", source="test")
    assert again.id == row.id
    assert "a@b.cl" not in row.value_hash
    assert row.value_hash == hashlib.sha256(b"a@b.cl").hexdigest()
    repo.add("phone", "+56 9 1111 2222", reason="baja", source="test")
    assert repo.contains("phone", "56911112222") is True


def test_settings_default_y_put(session: Session) -> None:
    repo = SettingsRepository(session)
    assert repo.get("ausente", default={"ok": False}) == {"ok": False}
    repo.put("quotas", {"scout": 3}, updated_by="test")
    assert repo.get("quotas") == {"scout": 3}
    repo.put("quotas", {"scout": 4}, updated_by="test")
    assert repo.get("quotas") == {"scout": 4}
    rows = list(session.scalars(select(Setting).where(Setting.key == "quotas")).all())
    assert len(rows) == 1


def test_claim_due_en_sqlite_y_skip_locked_solo_en_postgres(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead())
    now = datetime.now(UTC)
    due = Message(
        lead_id=lead.id,
        thread_id=lead.id,
        direction="out",
        channel="email_outreach",
        status="queued",
        scheduled_at=now - timedelta(minutes=5),
    )
    future = Message(
        lead_id=lead.id,
        thread_id=lead.id,
        direction="out",
        channel="email_outreach",
        status="queued",
        scheduled_at=now + timedelta(hours=2),
    )
    draft = Message(
        lead_id=lead.id,
        thread_id=lead.id,
        direction="out",
        channel="email_outreach",
        status="draft",
        scheduled_at=now - timedelta(minutes=5),
    )
    repo = MessageRepository(session)
    repo.add(due)
    repo.add(future)
    repo.add(draft)
    claimed = repo.claim_due(now=now)
    assert [item.id for item in claimed] == [due.id]

    postgres_sql = str(
        due_messages_statement(now, 10, dialect_name="postgresql").compile(
            dialect=postgresql.dialect()
        )
    )
    sqlite_sql = str(
        due_messages_statement(now, 10, dialect_name="sqlite").compile(dialect=sqlite.dialect())
    )
    assert "SKIP LOCKED" in postgres_sql.upper()
    assert "FOR UPDATE" in postgres_sql.upper()
    assert "SKIP LOCKED" not in sqlite_sql.upper()


def test_sqlite_abre_transaccion_inmediata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'lock.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_settings()
    reset_engine()
    engine = get_engine()
    seen: list[str] = []

    def _capture(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.commit()
    assert any("BEGIN IMMEDIATE" in statement for statement in seen)


def test_spend_job_y_derechos(session: Session) -> None:
    now = datetime.now(UTC)
    LlmCallRepository(session).add(
        LlmCall(
            agent="diagnoser",
            model="grok-4.7",
            prompt_name="diagnoser",
            prompt_version="2.0.0",
            tokens_in=10,
            tokens_out=5,
            cost_usd=Decimal("1.50"),
            latency_ms=20,
            ok=True,
            ts=now,
        )
    )
    LlmCallRepository(session).add(
        LlmCall(
            agent="diagnoser",
            model="grok-4.7",
            prompt_name="diagnoser",
            prompt_version="2.0.0",
            tokens_in=10,
            tokens_out=5,
            cost_usd=Decimal("9.00"),
            latency_ms=20,
            ok=False,
            ts=now - timedelta(days=3),
        )
    )
    assert LlmCallRepository(session).spend_today_usd(now=now) == Decimal("1.50")

    runs = JobRunRepository(session)
    run = runs.start("scout")
    assert run.status == "running"
    runs.finish(run, status="ok", processed=4)
    assert run.status == "ok"
    assert run.processed == 4
    assert run.finished_at is not None

    request = DataRequestRepository(session).add(
        kind="acceso",
        requester_email="persona@correo.cl",
        details="quiero una copia",
    )
    assert request.status == "open"
    remaining = request.due_at - datetime.now(UTC)
    assert timedelta(days=29) < remaining < timedelta(days=31)


def test_pago_idempotente(session: Session) -> None:
    lead = LeadRepository(session).add(make_lead())
    order = Order(
        lead_id=lead.id,
        package_code="landing_esencial",
        amount_clp=250_000,
        iva_clp=0,
        total_clp=250_000,
        deposit_percent=50,
        status="pending",
    )
    session.add(order)
    session.flush()
    first = PaymentRepository(session).add(
        Payment(
            order_id=order.id,
            provider="mercadopago",
            provider_payment_id="mp-1",
            status="approved",
            amount_clp=125_000,
        )
    )
    second = PaymentRepository(session).add(
        Payment(
            order_id=order.id,
            provider="mercadopago",
            provider_payment_id="mp-1",
            status="approved",
            amount_clp=125_000,
        )
    )
    assert first.id == second.id


def test_seed_dos_veces_no_duplica(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'seed.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_settings()
    reset_engine()
    assert seed_main() == 0
    assert seed_main() == 0
    with session_scope() as current:
        rows = list(current.scalars(select(Setting).where(Setting.key == "kill_switch")).all())
        assert len(rows) == 1
        assert rows[0].value is False
        SettingsRepository(current).put("kill_switch", True, updated_by="test")
    assert seed_main() == 0
    with session_scope() as current:
        row = current.get(Setting, "kill_switch")
        assert row is not None
        assert row.value is True


def test_alembic_upgrade_head(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'alembic.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    env = os.environ.copy()
    command = [sys.executable, "-m", "alembic", "upgrade", "head"]
    first = subprocess.run(
        command,
        cwd=ENGINE,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr + first.stdout
    second = subprocess.run(
        command,
        cwd=ENGINE,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr + second.stdout

    engine = create_engine(url)
    try:
        insp = inspect(engine)
        names = set(insp.get_table_names())
        assert set(Base.metadata.tables) <= names
        assert "alembic_version" in names
        for table_name, table in Base.metadata.tables.items():
            columns = {col["name"] for col in insp.get_columns(table_name)}
            assert columns == {column.name for column in table.columns}
    finally:
        engine.dispose()
