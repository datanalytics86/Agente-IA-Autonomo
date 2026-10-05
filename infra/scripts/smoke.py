#!/usr/bin/env python3
"""Smoke del stack (§7.2). Corre después de `docker compose up -d --build --wait`.

No levanta el compose: el job de CI lo hace antes. Sin Docker este script falla
y no inventa un healthz. La API de diagnóstico responde 202 (Accepted); el paso
5 lo acepta junto con 200 y exige que el lead aparezca en /api/leads.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "infra" / "docker-compose.yml"
ENV_FILE = ROOT / "infra" / ".env.ci"
BASE = "http://127.0.0.1"
COMPOSE = [
    "docker",
    "compose",
    "-f",
    str(COMPOSE_FILE),
    "--env-file",
    str(ENV_FILE),
]


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def run(args: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args), flush=True)
    completed = subprocess.run(
        args,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        fail(
            f"comando salió {completed.returncode}: {' '.join(args)}\n"
            f"stdout:\n{completed.stdout[-2000:]}\nstderr:\n{completed.stderr[-2000:]}"
        )
    return completed


def compose(*args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return run([*COMPOSE, *args], timeout=timeout)


def request(
    opener: urllib.request.OpenerDirector,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, urllib.request.Request, object, bytes]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json, text/html;q=0.9",
        "Accept-Encoding": "identity",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=20) as response:
            return response.status, response.headers, response, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc, exc.read()


def open_path(
    opener: urllib.request.OpenerDirector,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, object, bytes]:
    try:
        status, headers, _response, body = request(opener, method, path, payload)
    except urllib.error.URLError as exc:
        fail(f"{method} {path} no conectó: {exc.reason}")
    except OSError as exc:
        fail(f"{method} {path} no conectó: {exc}")
    return status, headers, body


def wait_until(label: str, probe, timeout_s: float) -> object:
    deadline = time.monotonic() + timeout_s
    last = "sin intento"
    while time.monotonic() < deadline:
        try:
            return probe()
        except SmokeFailure as exc:
            last = str(exc)
            time.sleep(3)
    fail(f"{label} no quedó listo en {timeout_s:.0f}s: {last}")
    return None


def json_body(body: bytes, path: str) -> object:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail(f"{path} no es JSON: {exc}; cuerpo={body[:200]!r}")
    return None


def header_value(headers: object, name: str) -> str:
    getter = getattr(headers, "get_all", None)
    if getter is None:
        return str(getattr(headers, "get", lambda _key, default="": default)(name, ""))
    values = getter(name) or []
    return ", ".join(str(item) for item in values)


def step_health(opener: urllib.request.OpenerDirector) -> None:
    def probe() -> tuple[object, object]:
        status, headers, body = open_path(opener, "GET", "/healthz")
        if status != 200:
            fail(f"/healthz status {status}: {body[:200]!r}")
        if b"<" in body or b"marcador" in body.lower():
            fail(f"/healthz parece HTML: {body[:200]!r}")
        ctype = header_value(headers, "Content-Type")
        if "json" not in ctype.lower():
            fail(f"/healthz content-type {ctype}")
        data = json_body(body, "/healthz")
        if data != {"status": "ok"}:
            fail(f"/healthz cuerpo {data!r}")
        status_r, headers_r, body_r = open_path(opener, "GET", "/readyz")
        if status_r != 200 or b"<" in body_r:
            fail(f"/readyz status {status_r}: {body_r[:200]!r}")
        if "json" not in header_value(headers_r, "Content-Type").lower():
            fail("/readyz no es JSON")
        ready = json_body(body_r, "/readyz")
        if not isinstance(ready, dict) or ready.get("status") != "ok":
            fail(f"/readyz cuerpo {ready!r}")
        return headers, headers_r

    wait_until("healthz/readyz", probe, 90)
    print("1 healthz y readyz ok", flush=True)


# El HTML viejo de infra/site-root decía «Sitio público (marcador)».
# El sitio real explica el placeholder de identidad y usa la palabra «marcador».
_STUB_MARKER = "sitio público (marcador)"


def step_site(opener: urllib.request.OpenerDirector) -> None:
    status, _headers, body = open_path(opener, "GET", "/")
    text = body.decode("utf-8", errors="replace")
    if status != 200:
        fail(f"GET / status {status}")
    if _STUB_MARKER in text.lower():
        fail("GET / sigue sirviendo el marcador")
    if "Landings para pymes locales" not in text:
        fail("GET / no trae el title del sitio Astro")
    print("2 sitio Astro ok", flush=True)


def step_admin(opener: urllib.request.OpenerDirector) -> None:
    for path in ("/admin/", "/admin/leads"):
        status, _headers, body = open_path(opener, "GET", path)
        text = body.decode("utf-8", errors="replace")
        if status != 200:
            fail(f"GET {path} status {status}")
        if "Agente IA Autónomo" not in text:
            fail(f"GET {path} no es el HTML del dashboard")
        if _STUB_MARKER in text.lower():
            fail(f"GET {path} contiene el marcador")
        refs = re.findall(r"""(?:src|href)=["']([^"']+)["']""", text)
        assets = [ref for ref in refs if ref.startswith("/admin/")]
        if not assets:
            fail(f"GET {path} no referencia assets /admin/")
        for ref in assets:
            asset_status, asset_headers, asset_body = open_path(opener, "GET", ref)
            if asset_status != 200:
                fail(f"GET {ref} status {asset_status}")
            ctype = header_value(asset_headers, "Content-Type").lower()
            if "text/html" in ctype or "Agente IA Autónomo" in asset_body[:400].decode(
                "utf-8", errors="replace"
            ):
                fail(f"GET {ref} devolvió el HTML del dashboard, no el asset")
    print("3 dashboard /admin ok", flush=True)


def step_admin_api(
    opener: urllib.request.OpenerDirector,
    jar: CookieJar,
    env: dict[str, str],
) -> None:
    created = compose("exec", "-T", "api", "python", "main.py", "--mode", "create-admin")
    text = created.stdout + created.stderr
    if "admin creado" not in text and "admin actualizado" not in text:
        fail(f"create-admin no confirmó el usuario: {text[-500:]}")
    email = env.get("ADMIN_EMAIL", "")
    password = env.get("ADMIN_PASSWORD", "")
    if not email or not password:
        fail("infra/.env.ci no trae ADMIN_EMAIL o ADMIN_PASSWORD")
    status, _headers, body = open_path(
        opener,
        "POST",
        "/api/auth/login",
        {"email": email, "password": password},
    )
    if status != 200:
        fail(f"login status {status}: {body[:300]!r}")
    if not any(cookie.name == "session" for cookie in jar):
        fail("login no dejó cookie de sesión")
    status, _headers, body = open_path(opener, "GET", "/api/leads")
    if status != 200:
        fail(f"GET /api/leads status {status}: {body[:300]!r}")
    payload = json_body(body, "/api/leads")
    if not isinstance(payload, dict) or "items" not in payload:
        fail(f"GET /api/leads cuerpo {payload!r}")
    print("4 login y /api/leads ok", flush=True)


def step_diagnostico(opener: urllib.request.OpenerDirector) -> str:
    payload = {
        "business": "Café Sur",
        "email": "persona@example.com",
        "commune": "Ñuñoa",
        "category": "cafeteria",
        "consent": True,
        "consent_text": "Acepto el tratamiento para el diagnóstico gratuito.",
        "website_url": None,
        "honeypot": "",
        "turnstile_token": "",
    }
    status, _headers, body = open_path(opener, "POST", "/api/public/diagnostico", payload)
    if status not in {200, 202}:
        fail(f"diagnostico status {status}: {body[:300]!r}")
    created = json_body(body, "/api/public/diagnostico")
    if not isinstance(created, dict) or not created.get("id"):
        fail(f"diagnostico sin id: {created!r}")
    lead_id = str(created["id"])
    status, _headers, body = open_path(opener, "GET", "/api/leads")
    listed = json_body(body, "/api/leads")
    items = listed.get("items") if isinstance(listed, dict) else None
    ids = {str(item.get("id")) for item in items or [] if isinstance(item, dict)}
    if lead_id not in ids:
        fail(f"el lead {lead_id} no está en /api/leads")
    print(f"5 diagnostico {status} lead {lead_id}", flush=True)
    return lead_id


def step_demo(opener: urllib.request.OpenerDirector) -> None:
    seeded = compose("exec", "-T", "api", "python", "seed_demo.py")
    token = ""
    for line in seeded.stdout.splitlines():
        if line.startswith("TOKEN="):
            token = line.split("=", 1)[1].strip()
    if not token:
        fail(f"seed_demo no imprimió TOKEN: {seeded.stdout[-400:]}")
    status, headers, body = open_path(opener, "GET", f"/demo/{token}")
    if status != 200:
        fail(f"GET /demo/{token} status {status}: {body[:200]!r}")
    robots = header_value(headers, "X-Robots-Tag").lower()
    if "noindex" not in robots:
        fail(f"/demo sin X-Robots-Tag noindex: {robots!r}")
    print("6 demo noindex ok", flush=True)


def step_alembic() -> None:
    heads = compose("exec", "-T", "api", "python", "-m", "alembic", "heads")
    revisions = re.findall(r"(?m)^([0-9a-f]{8,})\b", heads.stdout)
    if len(revisions) != 1:
        fail(f"alembic heads inesperado: {heads.stdout!r}")
    current = compose(
        "exec",
        "-T",
        "db",
        "sh",
        "-c",
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT version_num FROM alembic_version"',
    )
    version = current.stdout.strip()
    if version != revisions[0]:
        fail(f"alembic_version={version!r} head={revisions[0]!r}")
    print(f"7 alembic head {version}", flush=True)


def step_job_runs() -> None:
    def probe() -> str:
        counted = compose(
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM job_runs"',
        )
        raw = counted.stdout.strip()
        if not raw.isdigit() or int(raw) < 1:
            fail(f"job_runs={raw!r}")
        return raw

    total = wait_until("job_runs", probe, 120)
    print(f"8 job_runs={total}", flush=True)


def step_restart(opener: urllib.request.OpenerDirector, lead_id: str) -> None:
    compose("restart", timeout=240)

    def probe() -> None:
        status, _headers, body = open_path(opener, "GET", "/readyz")
        if status != 200:
            fail(f"readyz tras restart {status}")
        ready = json_body(body, "/readyz")
        if not isinstance(ready, dict) or ready.get("status") != "ok":
            fail(f"readyz tras restart {ready!r}")

    wait_until("readyz tras restart", probe, 120)
    status, _headers, body = open_path(opener, "GET", "/api/leads")
    if status != 200:
        fail(f"GET /api/leads tras restart {status}: {body[:200]!r}")
    listed = json_body(body, "/api/leads")
    items = listed.get("items") if isinstance(listed, dict) else None
    ids = {str(item.get("id")) for item in items or [] if isinstance(item, dict)}
    if lead_id not in ids:
        fail(f"el lead {lead_id} no persistió tras restart")
    print("9 datos persisten tras restart", flush=True)


def step_backup() -> None:
    compose("exec", "-T", "backup", "/usr/local/bin/backup.sh", "/backups", timeout=180)
    listed = compose(
        "exec",
        "-T",
        "backup",
        "bash",
        "-lc",
        "ls -1t /backups/agencia-*.dump",
    )
    paths = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    if not paths:
        fail("pg_dump no dejó archivos")
    compose("exec", "-T", "backup", "/usr/local/bin/restore.sh", paths[0], timeout=180)
    print(f"10 backup y restauracion {paths[0]}", flush=True)


def main() -> int:
    if not ENV_FILE.is_file():
        fail(f"falta {ENV_FILE}")
    env = load_env(ENV_FILE)
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    step_health(opener)
    step_site(opener)
    step_admin(opener)
    step_admin_api(opener, jar, env)
    lead_id = step_diagnostico(opener)
    step_demo(opener)
    step_alembic()
    step_job_runs()
    step_restart(opener, lead_id)
    step_backup()
    print("smoke ok", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"smoke fallo: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
