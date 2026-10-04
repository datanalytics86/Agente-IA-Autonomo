"""IMAP del buzón de outreach. La conexión ocurre dentro de `poll`, no al construir."""

from __future__ import annotations

import imaplib
from collections.abc import Callable
from email import message_from_bytes
from email import policy as email_policy
from typing import Protocol, cast

from core.config import Settings
from integrations.email.base import InboundMail
from integrations.errors import ProviderRequestError


class ImapClient(Protocol):
    def search_unseen(self) -> list[bytes]: ...

    def fetch(self, uid: bytes) -> bytes: ...

    def logout(self) -> None: ...


class StdlibImapClient:
    def __init__(self, settings: Settings) -> None:
        self._client = imaplib.IMAP4_SSL(settings.outreach_imap_host, settings.outreach_imap_port)
        self._client.login(settings.outreach_imap_user, settings.outreach_imap_password)
        self._client.select("INBOX")

    def search_unseen(self) -> list[bytes]:
        status, data = self._client.search(None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            return []
        return data[0].split()

    def fetch(self, uid: bytes) -> bytes:
        # El stub de IMAP4 pide str; en runtime el uid de SEARCH ya es bytes.
        status, data = self._client.fetch(cast(str, uid), "(RFC822)")
        if status != "OK" or not data:
            raise ProviderRequestError("imap no devolvió el mensaje")
        for item in data:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                return item[1]
        raise ProviderRequestError("imap no devolvió el mensaje")

    def logout(self) -> None:
        try:
            self._client.logout()
        except imaplib.IMAP4.error:
            return


def parse_rfc822(raw: bytes) -> InboundMail:
    message = message_from_bytes(raw, policy=email_policy.default)
    text = ""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not part.get_content_disposition():
                payload = part.get_content()
                text = payload if isinstance(payload, str) else str(payload)
                break
    else:
        payload = message.get_content()
        text = payload if isinstance(payload, str) else str(payload)
    return InboundMail(
        message_id=str(message["Message-ID"] or ""),
        from_addr=str(message["From"] or ""),
        to_addr=str(message["To"] or ""),
        subject=str(message["Subject"] or ""),
        text=text.strip(),
        in_reply_to=str(message["In-Reply-To"]) if message["In-Reply-To"] else None,
        intent="",
    )


class ImapPoller:
    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[[Settings], ImapClient] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory or StdlibImapClient
        self.connects = 0

    def poll(self) -> list[InboundMail]:
        if self.settings.dry_run or self.settings.app_mode != "prod":
            return []
        self.connects += 1
        client = self._client_factory(self.settings)
        try:
            found: list[InboundMail] = []
            for uid in client.search_unseen():
                found.append(parse_rfc822(client.fetch(uid)))
            return found
        finally:
            client.logout()


class FakeInbound:
    def __init__(self) -> None:
        self.queued: list[InboundMail] = []

    def enqueue(self, mail: InboundMail) -> None:
        self.queued.append(mail)

    def poll(self) -> list[InboundMail]:
        found = list(self.queued)
        self.queued.clear()
        return found
