"""Corre el worker real con el reloj saltando. No duerme y no abre sockets."""

from __future__ import annotations

import random
import socket
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from core.config import ENGINE_DIR, REPO_ROOT, reset_settings
from db.models import Base
from db.repositories import DataRequestRepository, SettingsRepository
from db.session import reset_engine
from simulation.providers import (
    FakeBooking,
    FakeInbound,
    FakeOutreach,
    FakePayments,
    FakePlaces,
    SilentNotifier,
    SimJudge,
    World,
    build_catalog,
)
from simulation.report import write_report
from worker.clock import FakeClock
from worker.jobs import JOBS
from worker.ports import JobContext, Ports
from worker.runner import execute
from worker.schedule import in_send_window, next_window_open, to_local, zone

SIM_START_LOCAL = datetime(2026, 3, 2, 0, 0, tzinfo=zone())
_ORDER = (
    "warmup_ramp",
    "demo_expiry",
    "data_retention",
    "scout",
    "hitl_digest",
    "data_requests_watch",
    "followups",
    "inbound_poll",
    "response_rate_guard",
    "pipeline_tick",
    "postventa",
    "metrics_rollup",
    "outreach_send",
)
_CRONS: tuple[tuple[int, int, str, Callable[[datetime], bool]], ...] = (
    (3, 0, "demo_expiry", lambda moment: True),
    (3, 30, "data_retention", lambda moment: True),
    (7, 0, "warmup_ramp", lambda moment: moment.weekday() == 0),
    (8, 0, "scout", lambda moment: moment.weekday() < 5),
    (8, 30, "hitl_digest", lambda moment: moment.weekday() < 5),
    (9, 0, "data_requests_watch", lambda moment: True),
    (10, 0, "followups", lambda moment: moment.weekday() < 5),
    (11, 0, "postventa", lambda moment: True),
    (17, 30, "hitl_digest", lambda moment: moment.weekday() < 5),
    (23, 55, "metrics_rollup", lambda moment: True),
)


def run_simulation(
    days: int = 14,
    seed: int = 42,
    *,
    report_path: Path | None = None,
    database_url: str | None = None,
) -> int:
    if days < 1:
        raise ValueError("days debe ser >= 1")
    reset_settings()
    start = SIM_START_LOCAL.astimezone(UTC)
    end = (SIM_START_LOCAL + timedelta(days=days)).astimezone(UTC)
    url = database_url or _default_database()
    engine = _engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    clock = FakeClock(start)
    world = World(rng=random.Random(seed))
    ports = _ports(world)
    path = report_path or (REPO_ROOT / "docs" / "simulacion" / f"reporte_seed{seed}_d{days}.md")
    guard = _SocketGuard()
    guard.install()
    session = Session(engine, expire_on_commit=False)
    try:
        _bootstrap(session, clock)
        session.commit()
        while clock.now() < end:
            ctx = JobContext(
                session=session,
                clock=clock,
                rng=world.rng,
                ports=ports,
            )
            for name in _due(clock.now(), session):
                execute(name, JOBS[name], ctx)
            session.commit()
            nxt = _next_moment(session, clock.now(), end)
            if nxt >= end:
                break
            clock.advance_to(nxt)
        world.network_calls = guard.calls
        code = write_report(
            session,
            path=path,
            seed=seed,
            days=days,
            started=start,
            finished=end,
            network_calls=guard.calls,
        )
        session.commit()
        return code
    finally:
        session.close()
        guard.restore()
        engine.dispose()
        reset_engine()


def _default_database() -> str:
    folder = ENGINE_DIR / "state"
    folder.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(folder / 'simulacion.db').as_posix()}"


def _engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=OFF")
        cursor.close()

    return engine


def _ports(world: World) -> Ports:
    catalog = build_catalog()
    return Ports(
        places=FakePlaces(catalog, world),
        outreach=FakeOutreach(world),
        inbound=FakeInbound(world),
        judge=SimJudge(),
        bookings=FakeBooking(),
        payments=FakePayments(),
        notifier=SilentNotifier(),
        network_calls=0,
    )


def _bootstrap(session: Session, clock: FakeClock) -> None:
    SettingsRepository(session).put("kill_switch", True, updated_by="simulacion")
    DataRequestRepository(session).add(
        kind="acceso",
        requester_email="persona@ejemplo.cl",
        details="simulación",
        due_at=clock.now() + timedelta(days=2),
    )


def _due(now: datetime, session: Session) -> list[str]:
    local = to_local(now)
    names: list[str] = []
    if local.second == 0 and local.microsecond == 0:
        if local.minute % 5 == 0:
            names.append("inbound_poll")
        if local.minute % 10 == 0:
            names.append("pipeline_tick")
        if local.minute == 0:
            names.append("response_rate_guard")
        for hour, minute, name, pred in _CRONS:
            if local.hour == hour and local.minute == minute and pred(local):
                names.append(name)
    if _outreach_due(session, now):
        names.append("outreach_send")
    unique = list(dict.fromkeys(names))
    return sorted(unique, key=_ORDER.index)


def _outreach_due(session: Session, now: datetime) -> bool:
    if not in_send_window(now):
        return False
    raw = SettingsRepository(session).get("next_outreach_at")
    if not isinstance(raw, str) or not raw:
        return True
    return _parse(raw) <= now


def _next_moment(session: Session, now: datetime, end: datetime) -> datetime:
    grid = _next_grid(now)
    scheduled = _future_outreach(session, now)
    nxt = min(grid, scheduled, end)
    if nxt <= now:
        nxt = min(now + timedelta(minutes=5), end)
    return nxt


def _next_grid(now: datetime) -> datetime:
    local = to_local(now).replace(second=0, microsecond=0)
    add = 5 - (local.minute % 5)
    if local.minute % 5 == 0:
        add = 5
    return (local + timedelta(minutes=add)).astimezone(UTC)


def _future_outreach(session: Session, now: datetime) -> datetime:
    raw = SettingsRepository(session).get("next_outreach_at")
    if isinstance(raw, str) and raw:
        scheduled = _parse(raw)
        if scheduled > now:
            return scheduled
    if in_send_window(now):
        return now + timedelta(minutes=5)
    return next_window_open(now + timedelta(seconds=1))


def _parse(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class _SocketGuard:
    """Cuenta y rechaza sockets que no sean loopback. Cero red en la simulación."""

    def __init__(self) -> None:
        self.calls = 0
        self._orig_connect = socket.socket.connect
        self._orig_connect_ex = socket.socket.connect_ex
        self._orig_create = socket.create_connection

    def install(self) -> None:
        guard = self

        def connect(sock: socket.socket, address: object) -> None:
            guard._reject(address)
            guard._orig_connect(sock, address)  # type: ignore[arg-type]

        def connect_ex(sock: socket.socket, address: object) -> int:
            guard._reject(address)
            return guard._orig_connect_ex(sock, address)  # type: ignore[arg-type]

        def create_connection(address: object, *args: object, **kwargs: object) -> socket.socket:
            guard._reject(address)
            return guard._orig_create(address, *args, **kwargs)  # type: ignore[arg-type]

        socket.socket.connect = connect  # type: ignore[method-assign, assignment]
        socket.socket.connect_ex = connect_ex  # type: ignore[method-assign, assignment]
        socket.create_connection = create_connection  # type: ignore[assignment]

    def restore(self) -> None:
        socket.socket.connect = self._orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = self._orig_connect_ex  # type: ignore[method-assign]
        socket.create_connection = self._orig_create  # type: ignore[assignment]

    def _reject(self, address: object) -> None:
        host = _host(address)
        if host is None or _loopback(host):
            return
        self.calls += 1
        raise RuntimeError(f"socket externo bloqueado en simulación: {host}")


def _host(address: object) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    if isinstance(address, str):
        return address
    return None


def _loopback(host: str) -> bool:
    bare = host.strip().strip("[]").split("%", 1)[0].lower().rstrip(".")
    return bare in {"localhost", "127.0.0.1", "::1"}
