"""Lock de instancia única y salida limpia si otra vive."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from core.config import reset_settings
from db.session import create_all, reset_engine, session_scope
from worker.cli import main
from worker.locking import LOCK_TTL, acquire_lock, refresh_lock
from worker.scheduler import build_scheduler


@pytest.fixture(autouse=True)
def _caches() -> object:
    reset_settings()
    reset_engine()
    yield
    reset_settings()
    reset_engine()


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> object:
    url = f"sqlite:///{(tmp_path / 'lock.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_settings()
    reset_engine()
    create_all()
    with session_scope() as current:
        yield current


def test_la_segunda_instancia_no_toma_el_lock(session: Session) -> None:
    now = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
    assert acquire_lock(session, "a", now) is True
    assert acquire_lock(session, "b", now + timedelta(seconds=10)) is False
    refreshed = now + timedelta(seconds=20)
    assert refresh_lock(session, "a", refreshed) is True
    assert acquire_lock(session, "b", refreshed + timedelta(seconds=30)) is False
    stale = refreshed + LOCK_TTL + timedelta(seconds=1)
    assert acquire_lock(session, "b", stale) is True


def test_main_sale_0_si_otra_instancia_vive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    url = f"sqlite:///{(tmp_path / 'main.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_settings()
    reset_engine()
    create_all()
    with session_scope() as current:
        acquire_lock(current, "otra", datetime.now(UTC))
    assert main() == 0
    captured = capsys.readouterr()
    assert "otra instancia" in captured.out.lower()


def test_scheduler_registra_los_jobs() -> None:
    scheduler = build_scheduler("test-owner")
    names = {job.id for job in scheduler.get_jobs()}
    assert {
        "scout",
        "pipeline_tick",
        "outreach_send",
        "followups",
        "inbound_poll",
        "response_rate_guard",
        "hitl_digest_am",
        "hitl_digest_pm",
        "warmup_ramp",
        "demo_expiry",
        "data_retention",
        "data_requests_watch",
        "metrics_rollup",
        "postventa",
        "heartbeat",
    } <= names
    if scheduler.running:
        scheduler.shutdown(wait=False)
