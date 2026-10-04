"""Auditor web. El fake no abre sockets y no inventa correos."""

from __future__ import annotations

import json
import re
import time
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urlencode, urljoin, urlparse

import httpx
from pydantic import BaseModel, Field

from core.config import Settings, get_settings

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COPYRIGHT_RE = re.compile(r"(?:©|\(c\)|copyright)\s*(20\d{2})", re.IGNORECASE)
_IG_SKIP = {"p", "reel", "reels", "explore", "stories", "accounts", "about"}
_PAGESPEED = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
_CMS = (
    ("wp-content", "wordpress"),
    ("wordpress", "wordpress"),
    ("wixstatic", "wix"),
    ("wix.com", "wix"),
    ("cdn.shopify", "shopify"),
    ("squarespace", "squarespace"),
    ("joomla", "joomla"),
    ("webflow", "webflow"),
)


class WebsiteAudit(BaseModel):
    url: str | None = None
    opportunity_score: int = Field(ge=0, le=100)
    https: bool | None = None
    has_viewport: bool | None = None
    copyright_year: int | None = None
    last_modified: str | None = None
    page_weight_bytes: int | None = None
    cms: str | None = None
    broken_links: list[str] = Field(default_factory=list)
    pagespeed_score: int | None = None
    contact_email: str | None = None
    contact_email_source_url: str | None = None
    instagram_handle: str | None = None
    source_url: str | None = None
    notes: list[str] = Field(default_factory=list)


class WebAuditor(Protocol):
    def audit(self, url: str | None) -> WebsiteAudit: ...


class FakeWebAuditor:
    """Sin red. Sin URL el score queda alto y el correo vacío."""

    def audit(self, url: str | None) -> WebsiteAudit:
        if not url:
            return WebsiteAudit(
                url=None,
                opportunity_score=88,
                contact_email=None,
                contact_email_source_url=None,
                instagram_handle=None,
                source_url=None,
                notes=["sin sitio: oportunidad alta"],
            )
        https = url.lower().startswith("https://")
        return WebsiteAudit(
            url=url,
            opportunity_score=62 if https else 74,
            https=https,
            contact_email=None,
            contact_email_source_url=None,
            instagram_handle=None,
            source_url=url,
            notes=["auditor fake: no abre sockets y no inventa correos"],
        )


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.viewport = False
        self.hrefs: list[str] = []
        self.mails: list[str] = []
        self.jsonld: list[str] = []
        self._script = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        if tag == "meta" and attr.get("name", "").lower() == "viewport":
            self.viewport = True
        if tag == "a":
            href = attr.get("href", "").strip()
            if href:
                self.hrefs.append(href)
                if href.lower().startswith("mailto:"):
                    self.mails.append(href.split(":", 1)[1].split("?", 1)[0])
        if tag == "script" and "ld+json" in attr.get("type", "").lower():
            self._script = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script:
            self.jsonld.append("".join(self._buf))
            self._script = False

    def handle_data(self, data: str) -> None:
        if self._script:
            self._buf.append(data)


class HttpWebAuditor:
    def __init__(
        self,
        *,
        user_agent: str,
        pagespeed_key: str = "",
        client: httpx.Client | None = None,
        min_interval: float = 1.0,
    ) -> None:
        self.user_agent = user_agent
        self.pagespeed_key = pagespeed_key
        self.min_interval = min_interval
        self._client = client
        self._owns = client is None
        self._last: dict[str, float] = {}

    def audit(self, url: str | None) -> WebsiteAudit:
        if not url:
            return FakeWebAuditor().audit(None)
        notes: list[str] = []
        client = self._client or httpx.Client(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        )
        try:
            if not self._robots_allow(client, url):
                notes.append("robots.txt no permite la página")
                return self._closed(url, notes)
            try:
                response = self._get(client, url)
            except httpx.HTTPError:
                notes.append("no se pudo leer la página")
                return self._closed(url, notes)
            if response.status_code >= 400:
                notes.append(f"home respondió {response.status_code}")
                return self._closed(url, notes)
            html = response.text
            weight = len(response.content)
            page = _Page()
            page.feed(html)
            email, email_source = self._find_email(client, url, page)
            handle = _instagram(page.hrefs)
            broken = self._broken(client, url, page.hrefs)
            year = _copyright(html)
            cms = _cms(html)
            speed = self._pagespeed(client, url)
            https = url.lower().startswith("https://")
            score = _score(
                https=https,
                viewport=page.viewport,
                year=year,
                weight=weight,
                broken=len(broken),
                pagespeed=speed,
            )
            return WebsiteAudit(
                url=url,
                opportunity_score=score,
                https=https,
                has_viewport=page.viewport,
                copyright_year=year,
                last_modified=response.headers.get("Last-Modified"),
                page_weight_bytes=weight,
                cms=cms,
                broken_links=broken,
                pagespeed_score=speed,
                contact_email=email,
                contact_email_source_url=email_source,
                instagram_handle=handle,
                source_url=email_source or url,
                notes=notes,
            )
        finally:
            if self._owns:
                client.close()

    def _closed(self, url: str, notes: list[str]) -> WebsiteAudit:
        https = url.lower().startswith("https://")
        return WebsiteAudit(
            url=url,
            opportunity_score=80,
            https=https,
            contact_email=None,
            contact_email_source_url=None,
            source_url=url,
            notes=notes,
        )

    def _get(self, client: httpx.Client, url: str) -> httpx.Response:
        host = urlparse(url).hostname or ""
        last = self._last.get(host)
        if last is not None and self.min_interval > 0:
            wait = self.min_interval - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        response = client.get(url)
        self._last[host] = time.monotonic()
        return response

    def _robots_allow(self, client: httpx.Client, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        robots = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            response = self._get(client, robots)
        except httpx.HTTPError:
            return False
        if response.status_code == 404:
            return True
        if response.status_code >= 400:
            return False
        path = parsed.path or "/"
        return _robots_allows(response.text, path)

    def _find_email(
        self,
        client: httpx.Client,
        page_url: str,
        page: _Page,
    ) -> tuple[str | None, str | None]:
        email = _first_email(page.mails, page.jsonld)
        if email:
            return email, page_url
        contact = _contact_href(page_url, page.hrefs)
        if contact is None or not self._robots_allow(client, contact):
            return None, None
        try:
            response = self._get(client, contact)
        except httpx.HTTPError:
            return None, None
        if response.status_code >= 400:
            return None, None
        nested = _Page()
        nested.feed(response.text)
        email = _first_email(nested.mails, nested.jsonld)
        if email:
            return email, contact
        return None, None

    def _broken(self, client: httpx.Client, page_url: str, hrefs: list[str]) -> list[str]:
        host = urlparse(page_url).hostname or ""
        broken: list[str] = []
        seen: set[str] = set()
        for href in hrefs:
            if href.startswith(("mailto:", "tel:", "#", "javascript:")):
                continue
            absolute = urljoin(page_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"} or parsed.hostname != host:
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            if len(seen) > 4:
                break
            try:
                response = self._get(client, absolute)
            except httpx.HTTPError:
                broken.append(absolute)
                continue
            if response.status_code >= 400:
                broken.append(absolute)
        return broken

    def _pagespeed(self, client: httpx.Client, url: str) -> int | None:
        if not self.pagespeed_key:
            return None
        query = urlencode({"url": url, "strategy": "mobile", "key": self.pagespeed_key})
        try:
            response = self._get(client, f"{_PAGESPEED}?{query}")
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        try:
            score = response.json()["lighthouseResult"]["categories"]["performance"]["score"]
        except (KeyError, TypeError, ValueError):
            return None
        if isinstance(score, (int, float)):
            return max(0, min(100, int(round(float(score) * 100))))
        return None


def build_auditor(settings: Settings | None = None) -> WebAuditor:
    current = settings or get_settings()
    if current.dry_run or current.app_mode == "demo":
        return FakeWebAuditor()
    base = current.public_base_url or "http://localhost"
    return HttpWebAuditor(
        user_agent=f"AgenciaBot/1.0 (+{base})",
        pagespeed_key=current.pagespeed_api_key,
    )


def _first_email(mails: list[str], blocks: list[str]) -> str | None:
    for raw in mails:
        clean = _clean_email(raw)
        if clean:
            return clean
    for block in blocks:
        for found in _emails_in_jsonld(block):
            return found
    return None


def _clean_email(raw: str) -> str | None:
    text = raw.strip().lower()
    if _EMAIL_RE.match(text):
        return text
    return None


def _emails_in_jsonld(raw: str) -> list[str]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() == "email" and isinstance(value, str):
                    clean = _clean_email(value)
                    if clean:
                        found.append(clean)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def _contact_href(page_url: str, hrefs: list[str]) -> str | None:
    for href in hrefs:
        lowered = href.lower()
        if "contacto" in lowered or "contact" in lowered:
            if lowered.startswith("mailto:"):
                continue
            return urljoin(page_url, href)
    return None


def _instagram(hrefs: list[str]) -> str | None:
    for href in hrefs:
        match = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?", href, re.IGNORECASE)
        if not match:
            continue
        handle = match.group(1).lstrip("@").lower()
        if handle in _IG_SKIP or len(handle) < 2:
            continue
        return handle
    return None


def _copyright(html: str) -> int | None:
    match = _COPYRIGHT_RE.search(html)
    if not match:
        return None
    return int(match.group(1))


def _cms(html: str) -> str | None:
    lowered = html.lower()
    for needle, name in _CMS:
        if needle in lowered:
            return name
    return None


def _robots_allows(text: str, path: str) -> bool:
    current = False
    disallows: list[str] = []
    for line in text.splitlines():
        clean = line.split("#", 1)[0].strip()
        if not clean or ":" not in clean:
            continue
        key, value = clean.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            current = value == "*"
        elif current and key == "disallow" and value:
            disallows.append(value)
    target = path or "/"
    return not any(target.startswith(rule) for rule in disallows)


def _score(
    *,
    https: bool,
    viewport: bool,
    year: int | None,
    weight: int,
    broken: int,
    pagespeed: int | None,
) -> int:
    score = 30
    if not https:
        score += 20
    if not viewport:
        score += 15
    if year is not None and year <= 2019:
        score += 15
    if weight > 1_000_000:
        score += 10
    score += min(15, 5 * broken)
    if pagespeed is not None and pagespeed < 50:
        score += 10
    return max(0, min(95, score))
