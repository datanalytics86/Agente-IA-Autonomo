"""Correo transaccional (Resend) y outreach (SMTP/IMAP) separados."""

from integrations.email.base import (
    InboundMail,
    InboundPoller,
    OutreachEmail,
    TransactionalEmail,
    build_inbound_poller,
    build_outreach_email,
    build_transactional_email,
    outreach_block_reason,
)
from integrations.email.inbound import FakeInbound, ImapPoller, parse_rfc822
from integrations.email.outreach import FakeOutreach, SmtpOutreach, build_outreach_message
from integrations.email.resend_mail import FakeTransactional, ResendTransactional

__all__ = [
    "FakeInbound",
    "FakeOutreach",
    "FakeTransactional",
    "ImapPoller",
    "InboundMail",
    "InboundPoller",
    "OutreachEmail",
    "ResendTransactional",
    "SmtpOutreach",
    "TransactionalEmail",
    "build_inbound_poller",
    "build_outreach_email",
    "build_outreach_message",
    "build_transactional_email",
    "outreach_block_reason",
    "parse_rfc822",
]
