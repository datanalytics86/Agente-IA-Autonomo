"""Publicación de sitios. Caddy copia a CLIENT_SITES_DIR; el dominio se valida aparte."""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import REPO_ROOT, Settings
from db.models import Project
from integrations.errors import ProviderRequestError

_PUBLISHED = frozenset({"aprobado", "publicado"})
CF_API = "https://api.cloudflare.com/client/v4"


def normalize_host(domain: str) -> str:
    raw = domain.strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    raw = raw.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0]
    if raw.startswith("www."):
        raw = raw[4:]
    return raw.rstrip(".")


def project_slug(project_id: str) -> str:
    raw = project_id.strip()
    if not raw or any(piece in raw for piece in ("..", "/", "\\", "\x00")):
        raise ValueError("project_id no es publicable")
    slug = "".join(char.lower() if char.isalnum() or char in {"-", "_"} else "-" for char in raw)
    slug = slug.strip("-")
    if not slug:
        raise ValueError("project_id no es publicable")
    return slug[:80]


def resolve_sites_dir(settings: Settings) -> Path:
    raw = Path(settings.client_sites_dir)
    if raw.is_absolute():
        return raw
    return (REPO_ROOT / raw).resolve()


class DomainPolicy:
    """`allowed_domains` ya viene filtrado. Con sesión, el status manda."""

    def __init__(
        self,
        allowed_domains: set[str] | None = None,
        session: Session | None = None,
    ) -> None:
        if allowed_domains is None:
            self.allowed: set[str] | None = None
        else:
            self.allowed = {host for item in allowed_domains if (host := normalize_host(item))}
        self.session = session

    def allows(self, domain: str) -> bool:
        host = normalize_host(domain)
        if not host:
            return False
        if self.session is not None:
            return _session_allows(self.session, host)
        if self.allowed is not None:
            return host in self.allowed
        return False


def _session_allows(session: Session, host: str) -> bool:
    rows = session.execute(select(Project.domain, Project.status)).all()
    for domain, status in rows:
        if status in _PUBLISHED and normalize_host(domain or "") == host:
            return True
    return False


def _require_domain(policy: DomainPolicy, domain: str | None) -> None:
    if domain is None:
        return
    if not policy.allows(domain):
        raise ValueError("dominio no autorizado")


def copy_site(sites_dir: Path, project_id: str, files: Path) -> Path:
    sites_dir.mkdir(parents=True, exist_ok=True)
    slug = project_slug(project_id)
    root = sites_dir.resolve()
    dest = (root / slug).resolve()
    if dest != root and root not in dest.parents:
        raise ValueError("destino de hosting inválido")
    if dest.exists():
        shutil.rmtree(dest)
    if files.is_dir():
        shutil.copytree(files, dest)
    elif files.is_file():
        dest.mkdir(parents=True)
        shutil.copy2(files, dest / files.name)
    else:
        raise FileNotFoundError(files)
    return dest


def zip_site(files: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if files.is_dir():
            for path in files.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(files).as_posix())
        elif files.is_file():
            archive.write(files, files.name)
        else:
            raise FileNotFoundError(files)
    return buffer.getvalue()


class SiteHosting(Protocol):
    def publish(self, project_id: str, files: Path, domain: str | None) -> str: ...

    def domain_allowed(self, domain: str) -> bool: ...


class CaddyHosting:
    def __init__(
        self,
        sites_dir: Path,
        *,
        allowed_domains: set[str] | None = None,
        session: Session | None = None,
    ) -> None:
        self.sites_dir = sites_dir
        self.policy = DomainPolicy(allowed_domains, session)

    def publish(self, project_id: str, files: Path, domain: str | None) -> str:
        _require_domain(self.policy, domain)
        return str(copy_site(self.sites_dir, project_id, files))

    def domain_allowed(self, domain: str) -> bool:
        return self.policy.allows(domain)


class CloudflarePagesHosting:
    def __init__(
        self,
        *,
        account_id: str,
        token: str,
        allowed_domains: set[str] | None = None,
        session: Session | None = None,
    ) -> None:
        self._account_id = account_id
        self._token = token
        self.policy = DomainPolicy(allowed_domains, session)

    def publish(self, project_id: str, files: Path, domain: str | None) -> str:
        _require_domain(self.policy, domain)
        slug = project_slug(project_id)
        response = httpx.post(
            f"{CF_API}/accounts/{self._account_id}/pages/projects/{slug}/deployments",
            headers={"Authorization": f"Bearer {self._token}"},
            files={"file": (f"{slug}.zip", zip_site(files), "application/zip")},
            timeout=30.0,
            trust_env=False,
        )
        if response.status_code not in {200, 201}:
            raise ProviderRequestError(f"cloudflare_{response.status_code}")
        result = (response.json().get("result") or {}) if response.content else {}
        deploy = str(result.get("url") or "")
        if not deploy:
            raise ProviderRequestError("cloudflare sin url")
        return deploy

    def domain_allowed(self, domain: str) -> bool:
        return self.policy.allows(domain)


class FakeHosting:
    def __init__(
        self,
        *,
        allowed_domains: set[str] | None = None,
        session: Session | None = None,
    ) -> None:
        self.policy = DomainPolicy(allowed_domains, session)
        self.published: list[tuple[str, str | None]] = []

    def publish(self, project_id: str, files: Path, domain: str | None) -> str:
        _require_domain(self.policy, domain)
        slug = project_slug(project_id)
        if not files.exists():
            raise FileNotFoundError(files)
        self.published.append((slug, domain))
        return f"fake://sites/{slug}"

    def domain_allowed(self, domain: str) -> bool:
        return self.policy.allows(domain)


def build_hosting(
    settings: Settings,
    *,
    allowed_domains: set[str] | None = None,
    session: Session | None = None,
) -> SiteHosting:
    if settings.app_mode == "demo" or settings.dry_run:
        return FakeHosting(allowed_domains=allowed_domains, session=session)
    if settings.hosting_provider == "cloudflare_pages":
        if not settings.cloudflare_api_token.strip() or not settings.cloudflare_account_id.strip():
            return FakeHosting(allowed_domains=allowed_domains, session=session)
        return CloudflarePagesHosting(
            account_id=settings.cloudflare_account_id,
            token=settings.cloudflare_api_token,
            allowed_domains=allowed_domains,
            session=session,
        )
    return CaddyHosting(
        resolve_sites_dir(settings),
        allowed_domains=allowed_domains,
        session=session,
    )
