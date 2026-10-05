"""Mapa de jobs de §8.5."""

from __future__ import annotations

from collections.abc import Callable

from worker.funnel import job_pipeline, job_scout
from worker.maintenance import (
    job_data_requests,
    job_demo_expiry,
    job_digest,
    job_metrics,
    job_postventa,
    job_retention,
)
from worker.ports import JobContext
from worker.sending import (
    job_diagnostico_gratis,
    job_followups,
    job_inbound,
    job_outreach,
    job_response_guard,
    job_warmup,
)

JOBS: dict[str, Callable[[JobContext], int]] = {
    "scout": job_scout,
    "pipeline_tick": job_pipeline,
    "outreach_send": job_outreach,
    "followups": job_followups,
    "inbound_poll": job_inbound,
    "diagnostico_gratis": job_diagnostico_gratis,
    "response_rate_guard": job_response_guard,
    "hitl_digest": job_digest,
    "warmup_ramp": job_warmup,
    "demo_expiry": job_demo_expiry,
    "data_retention": job_retention,
    "data_requests_watch": job_data_requests,
    "metrics_rollup": job_metrics,
    "postventa": job_postventa,
}
