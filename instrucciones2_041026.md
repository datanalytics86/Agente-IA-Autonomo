# instrucciones2_041026.md — Megaprompt ronda 2: de «demo verde» a «listo para deploy»

> **Destinatario:** Grok 4.7 (agente de código con shell, archivos y git).
> **Repositorio:** `datanalytics86/Agente-IA-Autonomo` · **Estado auditado:** `main` en `cb347d0` (merge del PR #2) · **Fecha:** 04-10-2026.
> **Contexto:** la ronda 1 (`instrucciones041026.md`) dejó 271 tests verdes, ruff/mypy limpios, sitio Astro, dashboard conectado y simulación de 14 días en 0 violaciones. Pero una auditoría independiente, **con Docker real**, encontró que el sistema **no arranca en Docker** y que **el worker de producción no usa ninguno de los adaptadores reales ni los agentes con IA**. Esta ronda cierra esas brechas.
> **Cómo usar:** dale a Grok este archivo completo y luego el **Mensaje de arranque** de la §10. `instrucciones041026.md` sigue vigente para todo lo que este archivo no cambie (guardrails legales §5, arquitectura §4, máquina de estados §8.2).

---

## 0. Misión

Eres **Grok 4.7**, **Integrador (B0)** de un enjambre de 7 agentes (B1–B7). Tu misión: dejar el sistema **listo para desplegar en un VPS con un solo comando**, de modo que al cargar credenciales reales en un `.env` el negocio funcione de punta a punta **sin cambiar código**:

1. `docker compose` levanta db, api, worker, sitio público, dashboard y proxy con TLS, y **sobrevive reinicios**.
2. En `APP_MODE=prod` el worker usa los **adaptadores reales** (Places, SMTP/IMAP, Resend, Cal.com/Calendly, Mercado Pago, Meta, hosting) y los **agentes con IA** (Diagnoser, Builder, Filmer, Checker, Mobile, Closer, Delivery, Reporter). Ningún stub en el camino de producción.
3. Un **smoke test automatizado** contra el stack Docker lo demuestra en CI.

«Casi 100 % listo» significa: lo único que falta para operar es lo que **solo el dueño** puede hacer (comprar dominio, crear cuentas, cargar claves, revisión legal). Todo lo demás es código probado.

---

## 1. Protocolo de ejecución (igual que la ronda 1, más estricto)

- **No pidas confirmación ni te detengas** entre tareas o fases. Terminas solo cuando la **DoD (§8)** está 100 % cumplida **con evidencia real** pegada en `docs/INFORME_FINAL_R2.md`.
- **Memoria:** `docs/PROGRESS_R2.md` (tablero de esta ronda). Actualízalo tras cada tarea. Si pierdes contexto, relee este archivo + `docs/PROGRESS_R2.md` y continúa desde la primera tarea pendiente.
- **Rama:** `grok/deploy-r2-041026` desde `main`. Commits pequeños, Conventional Commits en español. Al final, PR hacia `main` con el informe como descripción.
- **Protocolo de bloqueo:** el de `instrucciones041026.md` §1.2. Falta una credencial → adaptador probado con `respx`/fake + variable documentada + sigue.

### 1.1 Lecciones de la ronda 1 (prohibiciones nuevas)

Estas fallas pasaron todos los tests de la ronda 1. Quedan prohibidas y cada una tiene un test que la detecta (§7):

1. **Prohibido que un adaptador por defecto del worker sea un stub en `APP_MODE=prod`.** `EmptySource`, `GuardedOutreach` que siempre bloquea, `EmptyInbound`, `LogNotifier`, `LocalPayments` solo pueden existir en demo/tests.
2. **Prohibido tener dos pipelines.** El worker programado debe ejecutar los mismos agentes que el modo demo; no una copia simplificada que escribe placeholders.
3. **Prohibido registrar llamadas LLM ficticias** (`tokens_in=120`, `cost_usd=0.001` fijos) fuera de `FakeLlm`. `llm_calls` refleja solo llamadas reales o del fake explícito.
4. **Prohibido que un artefacto sea solo una fila en BD.** Si existe `artifacts.path`, el archivo existe en disco/almacenamiento y se puede servir.
5. **Prohibido avanzar un estado que depende de una persona sin la acción de esa persona** (p. ej. `en_revision_cliente → entregado` sin que el cliente apruebe en el portal).
6. **Prohibido presentar un `200` de HTML como evidencia de salud.** El healthcheck válido es el JSON `{"status":"ok"}` de la API (y `readyz` con BD).
7. **Prohibido marcar «solo falta Docker».** Si no hay Docker local, el job `compose-smoke` de GitHub Actions (que sí tiene Docker) es la evidencia obligatoria.

---

## 2. Hallazgos de la auditoría (verificados el 04-10-2026)

Verificación hecha: suite completa del motor (271 passed, cobertura 83 %), build y tests de `apps/site` y `apps/web`, y **`docker compose -f infra/docker-compose.yml up -d --build` ejecutado de verdad**.

### P0 — Bloquean el deploy

| # | Ubicación | Problema verificado |
|---|---|---|
| G1 | `engine/requirements.txt` | No incluye driver de Postgres ni PyYAML. En Docker, **api y worker caen al arrancar**: `ModuleNotFoundError: No module named 'psycopg'`. `requirements.txt` debe generarse desde `pyproject.toml` (y `pyproject` debe declarar `psycopg[binary]`) |
| G2 | `infra/Caddyfile`, `infra/site-root/` | Caddy sirve `infra/site-root/index.html` («Sitio público (marcador)») en vez del build de `apps/site`. **El sitio público no se despliega.** Además `/healthz` devuelve 200 porque `try_files` responde el HTML marcador: la «evidencia» de salud es falsa. La API real solo responde en `api:8000/healthz` |
| G3 | `apps/web/vite.config.ts`, `src/main.tsx`, Caddy/nginx | El dashboard se publica en `/admin` pero Vite no tiene `base: '/admin/'`, el router no tiene `basepath` y nginx no maneja el prefijo → `/admin` y `/admin/leads` dan **404** |
| G4 | `infra/Caddyfile`, `infra/docker-compose.yml` | `auto_https off` y solo `:80`: sin TLS, sin dominio, sin on-demand TLS para sitios de clientes. El directorio de sitios de clientes y `engine/output` no están montados ni servidos ni persistidos en volúmenes |
| G5 | `infra/docker-compose.yml` | Solo pasa 7 variables. No hay `env_file`; `SECRET_KEY`, credenciales, identidad de la agencia, etc. **nunca llegan** a api/worker. Postgres usa contraseña por defecto `agencia` |
| G6 | `engine/core/config.py:190`, `engine/api/security.py:78,98` | En `APP_MODE=prod` con `SECRET_KEY` vacío el proceso arranca y firma sesiones y tokens de baja con clave vacía → **sesiones de admin falsificables**. Igual con `ADMIN_PASSWORD_HASH` vacío e identidad de la agencia vacía (cae a «Agencia Demo», `worker/copywriter.py`) |
| G7 | `engine/api/app.py:27`, `engine/worker/cli.py:15` | El esquema se crea con `Base.metadata.create_all()`; Alembic existe pero nunca se ejecuta → las migraciones futuras no se aplican en prod |
| G8 | `infra/Dockerfile.engine`, CI | Imagen sin Chromium ni FFmpeg (Filmer nunca hace video en prod), sin `HEALTHCHECK`, sin herramienta para healthcheck; CI no construye la imagen ni levanta el stack |

### P0 — El núcleo autónomo está desconectado

| # | Ubicación | Problema verificado |
|---|---|---|
| G9 | `engine/worker/defaults.py` (`build_default_ports`) y `worker/scheduler.py:30` | El worker **siempre** usa stubs: `EmptySource` (Scout no encuentra nada), `GuardedOutreach` (devuelve `blocked` **incluso con el triple candado abierto y SMTP configurado**), `EmptyInbound` (no lee respuestas), `LocalBooking`, `LocalPayments`, `LogNotifier` (no avisa al dueño). Los adaptadores reales **existen y están testeados** en `integrations/` (`GooglePlacesSource`, `SmtpOutreach`, `ImapPoller`, `CalComBooking`, `CalendlyBooking`, `MercadoPagoProvider`, `MetaCloud`, `ResendTransactional`, `CaddyHosting`, `HttpWebAuditor`) pero **nada en el worker los construye** |
| G10 | `engine/worker/funnel.py` | **Segundo pipeline paralelo** que no llama a los agentes de `agents/`: el diagnóstico es un string fijo (`_diagnose`), la landing es una fila con `path` a un archivo que nunca se escribe (`_ensure_artifact`), el storyboard igual, `_charge_llm` inserta llamadas LLM ficticias (120 tokens, 0,001 USD) sin llamar a ningún modelo, y el outreach sale de una plantilla fija (`worker/copywriter.py`) en vez del pitch personalizado del Diagnoser. Los agentes reales solo corren en `--mode demo/cycle` |
| G11 | `engine/worker/funnel.py` `_one_step` | `en_produccion → en_revision_cliente → entregado` se ejecuta **solo** con razón «cliente aprueba», sin que el cliente apruebe; no genera la landing de producción, no publica (hosting no se usa), no cobra el saldo |
| G12 | `engine/worker/sending.py` `apply_inbound` | La intención se toma de `mail.intent`, que solo trae el proveedor fake. Con IMAP real no hay clasificación (Mobile + LLM) → **las respuestas reales nunca avanzan** a interesado/agendado; solo funciona el opt-out determinista |
| G13 | `engine/api/deps.py:113` | Busca `build_payment_provider` en `integrations.payments`, pero la función se llama `build_payments` → en prod **siempre** usa `LocalPaymentProvider`: el checkout nunca crea una preferencia real de Mercado Pago |
| G14 | `engine/api/services.py` `accept_signed_event` | `/webhooks/email` (rebotes y quejas de Resend) y `/webhooks/meta` (mensajes de IG/WhatsApp) verifican firma y **descartan** el evento: rebotes y quejas no entran a supresión; mensajes entrantes no llegan a Mobile |
| G15 | `engine/api/services.py` `_send_diagnostico_mail` | El «diagnóstico gratis» solo envía «Recibimos…»; **el informe prometido nunca se genera ni se envía**. Además `provider_message_id=f"tx-{lead.id}"` choca con el `UNIQUE` al segundo correo transaccional al mismo lead |
| G16 | `engine/api/services.py` `apply_payment` | Un pago aprobado del anticipo (50 %) marca la orden `paid` y pasa a producción; no existe cobro del saldo antes de publicar ni validación de monto pagado vs. esperado |
| G17 | `apps/site/src/**` | El sitio no incluye el widget de Turnstile, pero el backend lo exige si `TURNSTILE_SECRET_KEY` está definido → en prod los formularios fallan, o se despliega sin protección anti-bots |
| G18 | `engine/worker/defaults.py` `LogNotifier` | El digest HITL al dueño no se envía por ningún canal (email/Telegram) |

### P1 — Calidad y operación

| # | Ubicación | Problema |
|---|---|---|
| G19 | `engine/pyproject.toml` `[tool.mypy] exclude` | mypy excluye `agents/`, `api/`, `integrations/`, `simulation/`: los caminos de dinero y envío no tienen chequeo de tipos |
| G20 | cobertura | Caminos críticos con baja cobertura: `api/services.py` 60 %, `agents/closer.py` 31 %, `agents/delivery.py` 39 %, `api/security.py` 71 %, `api/yamlutil.py` 13 % |
| G21 | `.github/workflows/ci.yml` | El job `openapi` solo verifica que existan paths (no compara contra el contrato generado); no hay job Docker; los e2e de Playwright (`apps/web/e2e`) no corren en CI |
| G22 | `engine/simulation/` | La simulación de 14 días valida el pipeline de stubs. Tras G9–G12 debe validar el pipeline real (agentes + adaptadores reales con transporte fake) |
| G23 | operación | Backups no programados (scripts sueltos en `infra/scripts`), sin rotación verificada, sin restauración probada en Docker, sin alertas de error (Sentry opcional) ni heartbeat del worker visible |
| G24 | `docs/PROGRESS.md`, `docs/INFORME_FINAL.md` | Declaran la DoD casi completa («solo falta Docker»). Debe corregirse con el estado real |

---

## 3. Decisiones (fijas)

| Tema | Decisión |
|---|---|
| Composición prod | `infra/docker-compose.yml` (base) + `infra/docker-compose.prod.yml` (override: TLS, dominios, `restart: unless-stopped`, límites de recursos, sin puertos de db expuestos). `env_file: ../.env` en api y worker |
| Imágenes | `Dockerfile.engine` multi-stage con Chromium (Playwright) y FFmpeg en runtime, usuario no root, `HEALTHCHECK` con Python (`urllib`) contra `/healthz`. Imagen `site+web`: build multi-stage de `apps/site` y `apps/web` copiados a la imagen de Caddy (no montar `dist` del host) |
| Proxy | Caddy con `{$SITE_DOMAIN}` y `{$ADMIN_DOMAIN}` (o `/admin`), TLS automático, `on_demand_tls { ask http://api:8000/api/internal/domain-check }` para dominios de clientes, sitios de clientes servidos desde un volumen compartido `client_sites` |
| Rutas | `/` sitio Astro · `/admin/*` dashboard (Vite `base: '/admin/'`, router `basepath: '/admin'`) · `/api/*`, `/webhooks/*`, `/demo/*`, `/u/*` → api · `/healthz` y `/readyz` → api |
| Migraciones | `alembic upgrade head` al arrancar (servicio one-shot `migrate` del que dependen api y worker). `create_all()` solo en tests y SQLite demo |
| Config prod | Validador `fail-fast`: en `APP_MODE=prod` el proceso **no arranca** si faltan `SECRET_KEY` (≥ 32 chars), `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`, `PUBLIC_BASE_URL` https, `AGENCY_NAME`, `AGENCY_EMAIL`. Las credenciales de cada canal son opcionales: sin ellas ese canal queda deshabilitado **y visible como tal** en `/api/agents` y en el dashboard |
| Puertos del worker | Una sola fábrica `worker/wiring.py::build_ports(settings)` que en prod elige el adaptador real cuando hay credencial y un adaptador «deshabilitado» explícito cuando no (que registra evento `warn` una vez por día, no un stub silencioso). Los stubs actuales se mueven a `worker/testing_ports.py` y solo se usan en demo/tests/simulación |
| Pipeline único | El worker ejecuta los agentes de `agents/` (vía `agents/runtime.py`). Se elimina la lógica duplicada de `worker/funnel.py`; `funnel.py` queda como orquestador de cuotas/ventanas que **invoca** agentes |
| Simulación | Misma ruta de código que prod: agentes reales + adaptadores reales con transporte fake (`respx`, SMTP/IMAP fake, `FakeLlm`). Solo cambia la capa de transporte y el reloj |

---

## 4. Enjambre (B0–B7)

### 4.1 Roles y ownership

| ID | Rol | Hallazgos | Ownership exclusivo |
|---|---|---|---|
| **B0** | Integrador | G24, DoD | `docs/PROGRESS_R2.md`, `docs/INFORME_FINAL_R2.md`, `docs/DECISIONES.md`, `docs/contracts/`, `.env.example`, `engine/main.py` |
| **B1** | Infra y Deploy | G1, G2, G3 (lado proxy), G4, G5, G7 (servicio migrate), G8, G23 | `infra/`, `.dockerignore`, `engine/requirements.txt` (generado), job `compose-smoke` de CI |
| **B2** | Wiring de producción | G9, G13, G18 | `engine/worker/wiring.py`, `engine/worker/defaults.py`→`testing_ports.py`, `engine/worker/ports.py`, `engine/worker/scheduler.py`, `engine/api/deps.py`, `engine/integrations/**` (solo adaptaciones de interfaz) |
| **B3** | Pipeline único y entrega | G10, G11, G16 | `engine/worker/funnel.py`, `engine/worker/copywriter.py`, `engine/agents/**`, `engine/templates/**`, `engine/prompts/**`, funciones de pagos/proyectos en `engine/api/services.py` (`apply_payment`, `checkout`, `approve_project_public`, `_publish_project`) |
| **B4** | Inbound y webhooks | G12, G14, G15 | `engine/worker/sending.py`, `engine/api/routers/webhooks.py`, funciones de webhooks/diagnóstico en `engine/api/services.py` (`accept_signed_event`, `_send_diagnostico_mail`, `submit_diagnostico`, `submit_contacto`) |
| **B5** | Seguridad, config y front | G3 (lado app), G6, G17 | `engine/core/config.py`, `engine/api/security.py`, `engine/api/app.py`, `apps/site/`, `apps/web/` |
| **B6** | QA | G19, G20, G21, G22 | `engine/pyproject.toml` (sección mypy/pytest), `engine/tests/conftest.py`, `engine/simulation/`, `.github/workflows/ci.yml` (excepto job `compose-smoke` de B1), `apps/*/e2e/` |
| **B7** | Documentación | — | `README.md`, `docs/GO_LIVE.md`, `docs/RUNBOOK.md`, `docs/DEPLOY_VPS.md` (nuevo), `infra/README.md` |

`engine/api/services.py` es compartido por función: B3 y B4 solo editan sus funciones listadas; si necesitan otra, piden el cambio a B0 en `docs/contracts/CAMBIOS.md`. Cada agente escribe los tests de su código.

### 4.2 Olas

- **Ola 0 (B0):** crear rama, correr línea base (tests + intento de `docker compose up`), crear `docs/PROGRESS_R2.md` con G1–G24 y las tareas de §5, escribir el contrato de `build_ports` y de los puertos en `docs/contracts/integraciones.md`.
- **Ola 1 (paralelo):** B1 (Docker arranca: G1, G5, G7, G8) · B2 (wiring: G9, G13) · B5 (G6 fail-fast, G3 base path) · B6 (activar mypy en todo, e2e en CI).
- **Ola 2 (paralelo, depende de B2):** B3 (pipeline único, entrega, saldo) · B4 (inbound, webhooks, informe) · B1 (TLS, dominios, sitios de clientes, imagen front: G2, G4) · B5 (Turnstile en el sitio: G17).
- **Ola 3 (convergencia):** B6 simulación sobre el pipeline real + cobertura · B1 `compose-smoke` en CI + backups/restauración · B7 docs · B0 DoD.

Gate de merge (B0): ruff + mypy + pytest del paquete tocado, build de front si aplica, y para B1 el `compose-smoke` local o en CI.

---

## 5. Tareas detalladas

### B1 — Infra y Deploy
- [ ] **R2-B1-01** Declarar `psycopg[binary]` y `pyyaml` en `pyproject.toml`; generar `requirements.txt` con hashes o versiones fijadas desde `pyproject` (script `engine/scripts/lock.py` o `pip-compile`); test que falla si `requirements.txt` no contiene todo `[project].dependencies` (G1).
- [ ] **R2-B1-02** `Dockerfile.engine`: runtime con Chromium para Playwright + FFmpeg, `HEALTHCHECK` en Python, usuario no root, `.env` nunca copiado (G8).
- [ ] **R2-B1-03** `infra/Dockerfile.front`: build multi-stage de `apps/site` y `apps/web` (con `base: '/admin/'`) dentro de una imagen `caddy:2` (G2, G3).
- [ ] **R2-B1-04** Compose base + `docker-compose.prod.yml`: servicio `migrate` (`alembic upgrade head`) del que dependen api y worker; `env_file`; volúmenes `pgdata`, `artifacts` (montado en api y worker como `engine/output`), `client_sites`, `caddy_data`; `restart: unless-stopped`; db sin puertos públicos en prod; `POSTGRES_PASSWORD` obligatorio sin default en prod (G4, G5, G7).
- [ ] **R2-B1-05** Caddyfile con dominios por variable, TLS automático, `on_demand_tls` con `ask`, sitios de clientes desde `client_sites`, `/healthz`/`/readyz` a la api, `/admin` al dashboard, `/demo` con `X-Robots-Tag`, headers de seguridad (G2, G4).
- [ ] **R2-B1-06** Servicio `backup` (cron en contenedor) con `pg_dump` diario, rotación 14 días, y script de restauración probado en el smoke (G23).
- [ ] **R2-B1-07** `infra/scripts/smoke.py` (§7.2) y job `compose-smoke` en CI que construye y levanta el stack y corre el smoke (G8, prohibición 7).

### B2 — Wiring de producción
- [ ] **R2-B2-01** `worker/wiring.py::build_ports(settings)`: en `prod` mapea cada puerto al adaptador real de `integrations/` (adaptando tipos `worker.ports.*` ↔ `integrations.*`); sin credencial → `Disabled<Port>` explícito con evento diario; en `demo` → puertos de `testing_ports.py` (G9).
- [ ] **R2-B2-02** Outreach real: `SmtpOutreach` detrás del triple candado verificado **en el adaptador**; con candado cerrado devuelve `blocked` sin abrir sockets; con candado abierto entrega al transporte SMTP (test con transporte fake que verifica headers RFC 8058, `Reply-To` y cuerpo) (G9).
- [ ] **R2-B2-03** Inbound real: `ImapPoller` → `InboundMail` sin intención; la intención la pone B4 (G9, G12).
- [ ] **R2-B2-04** Places/auditor/booking/payments/hosting/meta/notifier reales en el wiring. Notifier: email transaccional al `NOTIFY_EMAIL` y Telegram si hay token (G9, G18).
- [ ] **R2-B2-05** `api/deps.py`: usar `integrations.payments.build_payments`; test que en prod con `MP_ACCESS_TOKEN` el proveedor es `MercadoPagoProvider` y en demo/dry-run el local (G13).
- [ ] **R2-B2-06** `/api/agents` y dashboard: estado de cada canal (`real`, `deshabilitado: falta X`, `dry_run`).

### B3 — Pipeline único y entrega
- [ ] **R2-B3-01** `worker/funnel.py` invoca los agentes (`Diagnoser`, `Builder`, `Filmer`, `Checker`, `Closer`, `Delivery`, `Reporter`) por `agents/runtime.py`; eliminar `_diagnose`, `_ensure_artifact` y `_charge_llm` ficticios; respetar cuotas, presupuesto LLM (desde `llm_calls` reales) y ventanas (G10).
- [ ] **R2-B3-02** Artefactos reales: landing demo HTML escrita en el volumen `artifacts` y servida por `/demo/{token}`; storyboard/video reales; test que todo `artifacts.path` existe (G10, prohibición 4).
- [ ] **R2-B3-03** Outreach con el pitch personalizado del Diagnoser (pasando por Checker v2), con la plantilla de `copywriter.py` solo como fallback cuando el LLM no está disponible (G10).
- [ ] **R2-B3-04** Entrega: `en_produccion` genera la landing de producción con el intake; `en_revision_cliente` espera la acción del cliente en el portal (aprobar/feedback con `max_revisions`); **solo** `approve_project_public` permite pasar a publicar (G11, prohibición 5).
- [ ] **R2-B3-05** Saldo: tras aprobación, si `deposit_percent < 100`, crear preferencia del saldo y publicar solo cuando el saldo esté pagado; validar en `apply_payment` que el monto pagado coincide con el esperado (anticipo o saldo) o crear approval `compliance` (G16).
- [ ] **R2-B3-06** Publicación con `build_hosting` (Caddy: copia a `client_sites/<slug>` + dominio verificado por `domain-check`), `entregado` con `deploy_url` real, email de entrega al cliente (G11).

### B4 — Inbound y webhooks
- [ ] **R2-B4-01** `apply_inbound`: opt-out determinista primero; luego clasificación con el agente Mobile (LLM, `mobile_classifier.md`) cuando el mensaje no trae intención; confianza baja → borrador HITL; prompt-injection → `otro` (G12).
- [ ] **R2-B4-02** `/webhooks/email`: `bounced`/`complained` → supresión + mensaje `bounced` + detener secuencia; `delivered` actualiza estado (G14).
- [ ] **R2-B4-03** `/webhooks/meta`: mensajes de IG/WhatsApp → `messages` inbound del lead (por handle/teléfono hash) → mismo `apply_inbound`; respuestas solo dentro de la ventana de 24 h (G14).
- [ ] **R2-B4-04** Diagnóstico gratis real: job que toma leads `inbound_diagnostico`, corre `HttpWebAuditor` + Diagnoser, renderiza informe HTML (Jinja2) y lo envía por email transaccional con link de agenda; `provider_message_id` único por mensaje (G15).

### B5 — Seguridad, config y front
- [ ] **R2-B5-01** Validador fail-fast de prod en `core/config.py` (§3) con mensaje claro de qué falta; test por cada variable (G6).
- [ ] **R2-B5-02** `apps/web`: `base: '/admin/'` en Vite, `basepath` en el router, `apiFetch` con rutas absolutas `/api`; e2e que navega `/admin/leads` (G3).
- [ ] **R2-B5-03** `apps/site`: widget Turnstile (site key desde `PUBLIC_TURNSTILE_SITE_KEY` en build) en diagnóstico, contacto, derechos y baja por formulario; sin key → los formularios funcionan y el backend no exige token (G17).
- [ ] **R2-B5-04** Identidad de la agencia en el sitio y en emails desde variables de build/entorno; en prod sin identidad el build del sitio falla con mensaje claro (G6, Ley 19.496).

### B6 — QA
- [ ] **R2-B6-01** mypy sobre todo el motor (strict en `core/`, `db/`, `worker/`; normal en `agents/`, `api/`, `integrations/`, `simulation/`), sin `ignore` masivos (G19).
- [ ] **R2-B6-02** Cobertura ≥ 85 % total y ≥ 80 % por archivo en `api/services.py`, `api/security.py`, `agents/closer.py`, `agents/delivery.py`, `worker/wiring.py` (G20).
- [ ] **R2-B6-03** CI: openapi-diff real (exportar y `git diff --exit-code`), e2e de Playwright de `apps/web` y del sitio, cache de pip/npm (G21).
- [ ] **R2-B6-04** Simulación de 14 días sobre el pipeline real (agentes + adaptadores reales con transporte fake). Mantener las aserciones de la ronda 1 y agregar las de §7.3 (G22).

### B7 — Documentación
- [ ] **R2-B7-01** `docs/DEPLOY_VPS.md`: paso a paso en un VPS Ubuntu (Docker, firewall, DNS, `.env`, `docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml up -d`, `create-admin`, backups, actualización y rollback), con variantes para el dueño en Windows (cómo conectarse por SSH).
- [ ] **R2-B7-02** `docs/GO_LIVE.md` actualizado: checklist del dueño en orden, cada credencial con dónde obtenerla y qué variable llena; plan de escalamiento gradual (modo sombra → semi-auto → auto).
- [ ] **R2-B7-03** `docs/RUNBOOK.md`: pausar (kill switch), revisar HITL, responder solicitudes de derechos, rotar claves, restaurar backup, leer logs.

### B0 — Integración
- [ ] **R2-B0-01** Corregir `docs/PROGRESS.md` e `docs/INFORME_FINAL.md` de la ronda 1 con una nota que remita a esta ronda (G24).
- [ ] **R2-B0-02** `.env.example` completo para prod (agrupado y comentado) + `infra/.env.ci` con valores de prueba para el smoke.
- [ ] **R2-B0-03** DoD con evidencia y PR final.

---

## 6. Guardrails (sin cambios respecto de la ronda 1)

Siguen vigentes íntegros los de `instrucciones041026.md` §5: Ley 21.719 / 19.628 / 19.496 art. 28 B, opt-out determinista y supresión global, RFC 8058, **sin DMs automatizados en frío por IG/LinkedIn/WhatsApp**, email outreach solo a direcciones publicadas por el negocio, landings demo `noindex` con banner y expiración, nada de testimonios inventados. Durante el desarrollo: **ningún envío, cobro ni publicación real**; los adaptadores reales se prueban con `respx` y transportes fake.

---

## 7. Tests obligatorios nuevos

### 7.1 Tests de regresión de la auditoría
- `test_prod_ports_no_son_stubs`: con `APP_MODE=prod` y todas las credenciales de prueba, `build_ports()` devuelve `GooglePlacesSource`, `SmtpOutreach`, `ImapPoller`, `CalComBooking`/`CalendlyBooking`, `MercadoPagoProvider`, notifier real; con credenciales vacías, `Disabled*` (nunca `Empty*`/`Local*`).
- `test_outreach_entrega_con_candado_abierto` y `test_outreach_bloquea_sin_socket_con_candado_cerrado`.
- `test_worker_y_demo_usan_los_mismos_agentes`: el job de pipeline invoca las clases de `agents/` (spy) y no existe `_charge_llm` ni strings de diagnóstico fijos.
- `test_artifacts_path_existe` para todo artefacto creado por el worker.
- `test_entrega_requiere_aprobacion_del_cliente` y `test_publica_solo_con_saldo_pagado`.
- `test_monto_pagado_distinto_crea_approval`.
- `test_imap_sin_intent_se_clasifica_con_mobile`.
- `test_webhook_email_bounce_suprime_y_detiene_secuencia`, `test_webhook_meta_crea_mensaje_inbound`.
- `test_diagnostico_gratis_envia_informe` y `test_dos_correos_tx_al_mismo_lead_no_chocan`.
- `test_prod_sin_secret_key_no_arranca` (y uno por cada variable obligatoria).
- `test_requirements_cubre_pyproject`.
- `test_checkout_prod_usa_mercadopago`.

### 7.2 Smoke del stack Docker (`infra/scripts/smoke.py`, corre en CI)
Con `infra/.env.ci` (`APP_MODE=demo`, `DRY_RUN=true`), tras `docker compose ... up -d --build --wait`:
1. `GET /healthz` → JSON `{"status":"ok"}` (no HTML); `GET /readyz` → BD conectada.
2. `GET /` → HTML del sitio Astro (contiene el `<title>` real, no «marcador»).
3. `GET /admin/` y `GET /admin/leads` → HTML del dashboard y sus assets `/admin/assets/*` con 200.
4. `docker compose exec api python main.py --mode create-admin` (no interactivo por env) → `POST /api/auth/login` → cookie de sesión → `GET /api/leads` 200.
5. `POST /api/public/diagnostico` → 200; el lead aparece en `/api/leads`.
6. `GET /demo/<token>` de un lead sembrado → 200 con `X-Robots-Tag: noindex`.
7. Tabla `alembic_version` existe y está en `head`.
8. El worker registra `job_runs` en < 2 min (heartbeat).
9. `docker compose restart` → los datos persisten.
10. Backup: `pg_dump` genera archivo y la restauración en una BD temporal funciona.

### 7.3 Aserciones nuevas de la simulación de 14 días
- 0 artefactos sin archivo · 0 `llm_calls` fuera de `FakeLlm` · 0 entregas sin aprobación del cliente · 0 publicaciones sin saldo pagado · 100 % de respuestas IMAP sin intención clasificadas por Mobile · 100 % de rebotes en supresión · al menos un informe de diagnóstico gratis enviado.

---

## 8. Definición de Terminado (evidencia en `docs/INFORME_FINAL_R2.md`)

- [ ] **A. Motor:** `cd engine && ruff check . && ruff format --check . && mypy . && pytest -q --cov --cov-fail-under=85` (mypy ya sin excluir `agents/api/integrations/simulation`).
- [ ] **B. Compatibilidad:** `python main.py --mode demo|status|prompts` siguen funcionando.
- [ ] **C. Front:** `apps/web`: lint, build, test, e2e. `apps/site`: build, test, e2e.
- [ ] **D. Docker (obligatorio):** `docker compose -f infra/docker-compose.yml --env-file infra/.env.ci up -d --build --wait` + `python infra/scripts/smoke.py` con los 10 pasos verdes, **localmente o en el job `compose-smoke` de CI** (link al run verde).
- [ ] **E. Prod config:** `docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config` válido; arrancar con `APP_MODE=prod` sin `SECRET_KEY` falla con mensaje claro (salida pegada).
- [ ] **F. Autonomía:** `python main.py --mode simulate --days 14 --seed 42` con 0 violaciones incluyendo §7.3, sobre el pipeline real.
- [ ] **G. Seguridad:** `pip-audit` y `npm audit --omit=dev` sin altas/críticas; escaneo de secretos limpio.
- [ ] **H. Docs:** `DEPLOY_VPS.md`, `GO_LIVE.md`, `RUNBOOK.md`, README actualizados; G1–G24 cerrados con commit y test en `PROGRESS_R2.md`.
- [ ] **I. CI verde** en la rama y PR abierto hacia `main`.

---

## 9. Lo que queda para el dueño (no es tarea de Grok)

Comprar dominio `.cl` y dominio secundario de outreach · VPS · DNS · buzón de outreach con SPF/DKIM/DMARC y warm-up · cuentas y claves (xAI, Google Places, PageSpeed, Resend, Cal.com/Calendly, Mercado Pago, Meta opcional, Turnstile, Telegram opcional) · datos de la agencia (nombre, RUT, email, dirección) · inicio de actividades SII · revisión legal de textos. Todo debe quedar listado, en orden y con la variable que llena, en `docs/GO_LIVE.md`.

---

## 10. Mensaje de arranque (pégalo a Grok después de este archivo)

```
Lee completo `instrucciones2_041026.md` en la raíz del repositorio (y usa `instrucciones041026.md` como referencia de guardrails y arquitectura). Eres B0, el Integrador.
Lanza el enjambre B1–B7 según la §4 (en paralelo si tu entorno lo permite; si no, en secuencia con el mismo ownership y gates).
Empieza ya por la Ola 0. No pidas confirmación y no te detengas: continúa hasta cumplir el 100 % de la DoD (§8) con evidencia real en docs/INFORME_FINAL_R2.md.
El smoke de Docker (§7.2) es obligatorio: si no tienes Docker local, el job compose-smoke de CI es la evidencia.
Respeta las prohibiciones de la §1.1 y los guardrails de la §6: nada de envíos, cobros ni publicaciones reales.
Si pierdes contexto, relee este archivo y docs/PROGRESS_R2.md y continúa desde la primera tarea pendiente.
```
