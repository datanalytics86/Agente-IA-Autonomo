"""APScheduler en America/Santiago. El proceso real no duerme dentro de los jobs."""

from __future__ import annotations

import random
from collections.abc import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from db.session import session_scope
from worker.clock import SystemClock
from worker.defaults import build_default_ports
from worker.jobs import JOBS
from worker.locking import refresh_lock
from worker.ports import JobContext
from worker.runner import execute

TZ = "America/Santiago"


def run_job(name: str) -> None:
    clock = SystemClock()
    with session_scope() as session:
        ctx = JobContext(
            session=session,
            clock=clock,
            rng=random.Random(),
            ports=build_default_ports(),
        )
        execute(name, JOBS[name], ctx)


def build_scheduler(owner: str) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=TZ)
    cron = CronTrigger

    def add_cron(
        job_id: str,
        name: str,
        *,
        day_of_week: str,
        hour: int | str,
        minute: int | str,
    ) -> None:
        scheduler.add_job(
            run_job,
            cron(
                day_of_week=day_of_week,
                hour=hour,
                minute=minute,
                timezone=TZ,
            ),
            id=job_id,
            args=[name],
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
        )

    add_cron("warmup_ramp", "warmup_ramp", day_of_week="mon", hour=7, minute=0)
    add_cron("scout", "scout", day_of_week="mon-fri", hour=8, minute=0)
    add_cron("hitl_digest_am", "hitl_digest", day_of_week="mon-fri", hour=8, minute=30)
    add_cron("hitl_digest_pm", "hitl_digest", day_of_week="mon-fri", hour=17, minute=30)
    add_cron("followups", "followups", day_of_week="mon-fri", hour=10, minute=0)
    add_cron("data_requests_watch", "data_requests_watch", day_of_week="*", hour=9, minute=0)
    add_cron("postventa", "postventa", day_of_week="*", hour=11, minute=0)
    add_cron("demo_expiry", "demo_expiry", day_of_week="*", hour=3, minute=0)
    add_cron("data_retention", "data_retention", day_of_week="*", hour=3, minute=30)
    add_cron("metrics_rollup", "metrics_rollup", day_of_week="*", hour=23, minute=55)
    add_cron(
        "outreach_send",
        "outreach_send",
        day_of_week="mon-fri",
        hour="9-18",
        minute="*",
    )
    scheduler.add_job(
        run_job,
        IntervalTrigger(minutes=10, timezone=TZ),
        id="pipeline_tick",
        args=["pipeline_tick"],
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        run_job,
        IntervalTrigger(minutes=5, timezone=TZ),
        id="inbound_poll",
        args=["inbound_poll"],
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        run_job,
        IntervalTrigger(hours=1, timezone=TZ),
        id="response_rate_guard",
        args=["response_rate_guard"],
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        _heartbeat,
        IntervalTrigger(seconds=30, timezone=TZ),
        id="heartbeat",
        args=[owner],
        coalesce=True,
        max_instances=1,
    )
    return scheduler


def _heartbeat(owner: str) -> None:
    from datetime import UTC, datetime

    with session_scope() as session:
        refresh_lock(session, owner, datetime.now(UTC))


Dispatch = Callable[[str], None]
