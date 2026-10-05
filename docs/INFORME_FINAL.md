# Informe final — autonomía 04-10-2026

> Ronda 2 (`instrucciones2_041026.md`, rama `grok/deploy-r2-041026`): esta ronda 1 dejó el demo verde, pero el stack Docker no arranca y el worker de producción no usa los adaptadores ni los agentes reales. El estado de deploy está en `docs/PROGRESS_R2.md` y el cierre irá en `docs/INFORME_FINAL_R2.md`. No tomar este archivo como «solo falta Docker».

Rama `grok/autonomia-041026`. Integrador A0. La evidencia de abajo es la salida de los comandos corridos en esta máquina el 2026-10-04. Donde un comando no pudo correr, se pega el error real.

## Qué se hizo

Fase 0 fijó contratos, tablero y decisiones. Las olas 1 y 2 quedaron integradas hasta `ea42023` (núcleo, compliance, CI, API, agentes, worker, canales, dashboard y sitio). El cierre conecta el recorrido público: diagnóstico con correo transaccional falso, agenda firmada, checkout falso, pago, intake, vista previa y copia del HTML a `CLIENT_SITES_DIR/<slug>`. ADR-012 agrega el arco `diagnosticado → agendado` para esa agenda. ADR-013 deja `mypy .` estricto en `core`, `db` y `worker`.

La cola `state/queue.json` ya no se crea. El umbral de alto valor sale de `hitl_value_clp`. La constante suelta `HIGH_VALUE_CLP` se retiró.

## Arquitectura

- `engine/`: agentes, API FastAPI, worker APScheduler (`America/Santiago`) y simulación con reloj falso. SQLite por defecto. Postgres 16 en el Compose.
- `apps/web/`: panel React. Cookie HttpOnly y CSRF. Zustand solo de interfaz.
- `apps/site/`: Astro. Identidad pública `[datos de la agencia]` hasta que el entorno la defina.
- `infra/`: Dockerfile del motor, Compose y Caddy. En esta máquina no hay binario `docker`, así que ese stack no se levantó.

Demo sin credenciales: `APP_MODE=demo`, `DRY_RUN=true`, `OUTREACH_ENABLED=false`, kill switch en falso. No hay envío real, ni cobro real, ni DM automático de Instagram o LinkedIn. Esos dos canales quedan en `manual_pending`.

## Cómo correr

Demo, API, worker y simulación: `docs/RUNBOOK.md`. Puesta en producción: `docs/GO_LIVE.md`. El dueño completa nombre, RUT y dirección fuera del repositorio.

## A. Motor

Comando, en `engine/` con el venv, después de retirar la cola JSON:

```
ruff check .
ruff format --check .
mypy .
pytest -q --cov=core --cov=agents --cov=worker --cov-fail-under=80
```

Salida:

```
All checks passed!
RUFF=0
140 files already formatted
FMT=0
Success: no issues found in 29 source files
MYPY=0
271 passed, 1 warning in 94.06s
Required test coverage of 80% reached. Total coverage: 86.15%
PYTEST=0
```

`mypy .` revisa 29 archivos. ADR-013 excluye `agents`, `api`, `integrations`, `simulation`, `tests`, `migrations` y `main.py`. Esos paquetes no están limpios de anotaciones. El comando pedido sale 0 porque el núcleo estricto está limpio.

Cobertura combinada 86.15 %. `agents/closer.py` queda en 31 % y `agents/delivery.py` en 39 %. El umbral del comando es el total, y ese total pasa.

`python main.py --mode demo` y `--mode status` (misma corrida, exit 0 los dos):

```
✓ Ciclo DEMO completado
Scout: 3 leads
Diagnoser: 3 · Builder: 3 · Filmer: 3
Checker: 2 · Pitcher: 0
HTML en output/: 9 · Storyboards: 9
High-value → status revision (HITL, sin envío automático)
DEMO=0
STATUS=0
```

Tabla de esa corrida: 6 leads en `revision`. Alto valor solo en Clínica Dental Santa Lucía y Clínica Dental El Roble, las dos a 2.800.000 CLP. Peluquería, óptica y el estudio jurídico no llevan la marca. El Filmer avisó `sin Chromium o FFmpeg: storyboard Markdown`. El LLM avisó `fallback determinista (sin_key)`.

`migrate-json` dos veces:

```
resumen leads_ok=3 leads_invalidos=0 leads_ya_existentes=0 events_ok=24 events_invalidos=0 events_ya_existentes=0
MIGRATE1=0
resumen leads_ok=0 leads_invalidos=0 leads_ya_existentes=3 events_ok=0 events_invalidos=0 events_ya_existentes=24
MIGRATE2=0
```

La segunda pasada no inserta de nuevo.

## B. Dashboard

En `apps/web`:

```
oxlint
Found 0 warnings and 0 errors.
WEB_LINT=0
vite v8.1.5 building client environment for production...
✓ built in 9.09s
WEB_BUILD=0
Test Files  2 passed (2)
     Tests  5 passed (5)
WEB_TEST=0
```

## C. Sitio

En `apps/site`:

```
32 page(s) built in 1.57s
SITE_BUILD=0
# tests 5
# pass 5
# fail 0
SITE_TEST=0
```

Lighthouse móvil (Edge, `--form-factor=mobile`) contra un servidor HTTPS local que sirve `apps/site/dist` y una landing renderizada con `render_theme("servicios", demo=False)`. El certificado es de esa medición. Las cabeceras copian el bloque `:80` de `infra/Caddyfile` y agregan `Strict-Transport-Security: max-age=300` porque la URL era HTTPS. No pasó por Docker.

```
HOME_HTTP=200
LH_HOME=0
LH_LANDING=0
lh-home     performance 100  accessibility 100  best-practices 100  seo 100
lh-landing  performance 100  accessibility 100  best-practices 96   seo 100
```

El 96 de la landing es el audit `errors-in-console`: el navegador pidió `/favicon.ico` y el servidor respondió 404. Las cuatro categorías quedan en 90 o más.

## D. Integración

`docker version` en esta máquina:

```
"docker" no se reconoce como un comando interno o externo,
programa o archivo por lotes ejecutable.
```

`docker compose -f infra/docker-compose.yml up -d --build` no se ejecutó. `curl http://localhost/healthz` a través de Compose no tiene respuesta que pegar. El Compose y el Caddyfile están en `infra/`. El workflow de CI no trae job de Docker por la misma razón.

Lo que sí corrió, en `apps/web`:

```
npx playwright test --config e2e/playwright.config.ts
  ✓  e2e\smoke.spec.ts › el HTML del build contiene el título del dashboard
  ✓  e2e\venta.spec.ts › diagnóstico, agenda, checkout falso, portal y sitio publicado
  ✓  e2e\venta.spec.ts › login y aprobar un HITL de alto valor
  3 passed (8.6s)
E2E=0
```

El recorrido usa SQLite desechable, webhook de calendario con firma, checkout falso y webhook de Mercado Pago con firma. El texto del pago dice que no se hizo ningún cobro. El login de admin y la aprobación HITL pasan en el tercer test. `X-Robots-Tag: noindex, nofollow` en `/demo/<token>` y en la vista previa lo afirman `test_demo_html_y_expirada` y `test_flujo_publico_diagnostico_hasta_sitio`, dentro de los 271 tests.

## E. Simulación

```
python main.py --mode simulate --days 14 --seed 42
SIM=0
```

`docs/simulacion/reporte_seed42_d14.md` cierra así:

```
- enviados: 35
- rebotes: 1
- ingresos_clp: 175000
- canal_pausado: email_outreach
- approvals: deal_alto_valor=1, tasa_respuesta_baja=1
- llamadas_de_red: 0

- todas las aserciones de la sección 10 pasan

violaciones: 0
```

El canal de outreach en frío queda pausado por la tasa de respuesta. El default del 12 % no se bajó.

## F. Compliance y seguridad

Los 271 tests incluyen `test_compliance.py`, `test_email.py`, `test_meta.py` y `test_secret_scan.py` (`test_el_arbol_no_contiene_secretos`). Instagram y LinkedIn en frío quedan en `manual_pending`. El dry-run no dispara los mocks de red.

`pip-audit` (el paquete local `agencia-engine` no está en PyPI y el informe lo salta):

```
No known vulnerabilities found
```

`npm audit --omit=dev` en `apps/web` y en `apps/site`:

```
found 0 vulnerabilities
```

`npm audit` completo del dashboard, con devDependencies, reporta una alta: `nanoid` &lt; 3.3.18, GHSA-2v37-7h3g-55p8, CVSS 5.9, generadores custom con `size` 0. No aparece al omitir dev. No se corrió `npm audit fix`.

`docs/compliance/AUDITORIA.md` está firmada como revisión de ingeniería por A0 en el rol de cierre de A8, con fecha 2026-10-04. No es dictamen y no habilita envíos. Las casillas de abogado siguen abiertas. `docs/compliance/REVISION_LEGAL.md` tiene las preguntas para un abogado. `docs/security/THREAT_MODEL.md` describe API, webhooks, datos y panel.

La casilla de opt-out en el mismo ciclo sigue abierta en la auditoría: no hay un test de un ciclo completo que corte la secuencia.

## G. Documentación

Están el README de la raíz, `apps/web/README.md`, `docs/RUNBOOK.md`, `docs/GO_LIVE.md` y este informe. H1–H30 están en `docs/PROGRESS.md` con el commit y el test que los cubre.

## Hallazgos H1–H30

| ID | Cierre | Test o evidencia |
|----|--------|------------------|
| H1 | `fc72ffb` | `test_json_invalido_no_se_reescribe` |
| H2 | `fc72ffb` | `test_load_leads_reporta_filas_invalidas` |
| H3 | `fc72ffb` | la base es la fuente; `migrate-json` no reescribe el origen |
| H4 | `8ed6259` | `test_agents_no_asignan_status`, `test_no_hay_asignacion_de_status_fuera_de_core_y_agents` |
| H5 | `f96f839` | `test_aprobar_hitl_vuelve_a_paused_from` |
| H6 | `8ed6259` y `e0868d6` | `hitl_value_clp`, `response_rate_guard`; se quitó `HIGH_VALUE_CLP` |
| H7 | `c905390` | Jinja2 `select_autoescape`; `test_temas_mapean_rubros_y_no_filtran_el_id` |
| H8 | `d65f02f` | `test_rechaza_testimonio_inventado` |
| H9 | `c905390` | `booking_link` desde configuración |
| H10 | `c905390` | el mismo test de temas exige que el HTML no lleve `lead_` |
| H11 | `d09f330` | el demo imprime `fallback determinista (sin_key)` |
| H12 | `c905390` | `test_alto_valor_forzado_solo_en_demo_y_rubro` |
| H13 | `ec40161` | `test_frio_no_se_envia` |
| H14 | `d65f02f` | `test_compliance.py` revisa el mensaje |
| H15 | `c905390` | el ciclo no duplica el HITL ni crea leads |
| H16 | `c905390` | `test_run_cycle_no_crea_leads_y_respeta_cuota` |
| H17 | `c905390` | `test_mobile_solo_loguea_un_mensaje_nuevo` |
| H18 | `fc72ffb` | eventos en la base; ya no está `MAX_LOGS` |
| H19 | `e0868d6` | `test_la_cola_json_no_se_crea` |
| H20 | `8ed6259` | `LLM_MODEL=grok-4.7` y alias `GROK_API_KEY` |
| H21 | `4a17816` | `test_metrics_salen_de_la_base` |
| H22 | `4a17816` | `test_aprobar_hitl_vuelve_a_paused_from` |
| H23 | `f96f839` | `test_editar_deja_el_mensaje_en_checking` |
| H24 | `4a17816` | el panel lee la API; `mock.ts` solo lo importa un test |
| H25 | `f96f839` | `test_kill_switch_persiste_y_app_mode_es_de_solo_lectura` |
| H26 | `4a17816` | métricas desde la base, incluido el gasto LLM |
| H27 | `80f5188` | `test_login_cookie_y_csrf` |
| H28 | `4ae5920` | el README no trae rutas de `T14 Gen 2` |
| H29 | `e0868d6` | `apps/web/README.md` describe las rutas reales |
| H30 | `84a1202`, `ae2635e` | tests, ruff, mypy, CI y Compose. El binario docker no está en esta máquina |

## Riesgos y deuda

- Compose sin evidencia de arranque en esta máquina. El healthcheck de producción queda para un host con Docker.
- `mypy` no cubre agentes ni API. ADR-013 lo deja escrito.
- Closer y Delivery por debajo del 80 % individual. El total pasa.
- La vista previa publicada por el portal es HTML mínimo (nombre, comuna, noindex). La landing de Lighthouse salió de la plantilla Jinja con `demo=False`.
- Opt-out del mismo ciclo sin test de punta a punta.
- Revisión legal abierta. Identidad de la agencia vacía a propósito.
- `nanoid` alto solo en dependencias de desarrollo.
- El job de CI no ejecuta Playwright ni Docker. Sí ejecuta ruff, formato, mypy, la cobertura, una simulación de 3 días y `npm test` del sitio.

## Próximos pasos

1. Instalar Docker y pegar el `healthz` de Compose.
2. Llevar la firma de `AUDITORIA.md` a un abogado, con `REVISION_LEGAL.md`.
3. Anotar el favicon de la plantilla Jinja para quitar el 404 de consola.
4. Recién con identidad, SII y la revisión legal, seguir `docs/GO_LIVE.md`. El código sigue en demo.
