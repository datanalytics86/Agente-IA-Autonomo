"""Auditoría web y PageSpeed."""

from integrations.pagespeed.base import (
    FakeWebAuditor,
    HttpWebAuditor,
    WebAuditor,
    WebsiteAudit,
    build_auditor,
)

__all__ = [
    "FakeWebAuditor",
    "HttpWebAuditor",
    "WebAuditor",
    "WebsiteAudit",
    "build_auditor",
]
