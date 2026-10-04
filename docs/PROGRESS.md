# PROGRESS — Autonomía 04-10-2026

Rama: `grok/autonomia-041026` · Última actualización: 2026-10-04 18:45 America/Santiago · Ola actual: 3

## Estado de la DoD

A ✅ · B ✅ · C ✅ · D ⛔ · E ✅ · F ✅ · G ✅

D está en ⛔ porque `docker` no es un comando en esta máquina. El detalle y la salida están en `docs/INFORME_FINAL.md`. La rama está en origin y el PR es https://github.com/datanalytics86/Agente-IA-Autonomo/pull/2.

## Línea base F0-02 (commit de partida `19b678b`, Python 3.12.10, Node 22.23.2)

Comando: `engine\.venv\Scripts\python.exe main.py --mode demo` (exit 0).

- Leads: `enviado` 2, `revision` 1, total 3.
- High-value: Gimnasio boutique Santa Lucía, Ñuñoa, 2.932.741 CLP, status `revision`.
- Resumen del propio comando: Scout 3, Diagnoser 3, Builder 3, Filmer 3, Checker 3, Pitcher 2.
- Artefactos en disco: 3 HTML y 3 `storyboard_*.md`.
- `python main.py --mode status` repitió la misma tabla (exit 0).
- `python main.py --mode prompts` listó 8 prompts (exit 0) después del gancho de modos nuevos.

Web, en `apps/web`:

- `npm.cmd ci` exit 0 (152 paquetes). Aviso previo: 1 vulnerabilidad high. Sigue en devDependencies (`nanoid` &lt; 3.3.18, GHSA-2v37-7h3g-55p8). `npm audit --omit=dev` sale en 0.
- `npm.cmd run lint` exit 0.
- `npm.cmd run build` exit 0.

Esa línea base ya no describe el árbol actual. El demo de cierre tiene 6 leads en `revision` y el alto valor solo en rubros de la lista.

## Tablero

| ID | Tarea | Agente | Estado | Commit | Evidencia |
|----|-------|--------|--------|--------|-----------|
| F0-01 | Crear rama desde main | A0 | ✅ | 0d89efa | `grok/autonomia-041026` sobre `19b678b` |
| F0-02 | Línea base §2.2 | A0 | ✅ | 0d89efa | tablas de esta sección |
| F0-03 | Contratos §6.3 | A0 | ✅ | 0d89efa | `docs/contracts/` |
| F0-04 | Tablero | A0 | ✅ | 0d89efa | este archivo |
| F0-05 | DECISIONES y GO_LIVE | A0 | ✅ | 0d89efa | `docs/DECISIONES.md`, `docs/GO_LIVE.md` |
| F1-01 | pyproject + requirements | A1 | ✅ | 7ede130 | ruff, mypy y pytest del núcleo |
| F1-02 | core/config.py | A1 | ✅ | 8ed6259 | alias GROK_API_KEY |
| F1-03 | modelos, Alembic, repos | A1 | ✅ | fc72ffb | revisión 2fb1d83b32e1 |
| F1-04 | transition() única | A1 | ✅ | 8ed6259 | `test_agents_no_asignan_status` |
| F1-05 | migrate-json | A1 | ✅ | fc72ffb | segunda pasada `leads_ya_existentes=3` |
| F1-06 | agentes sobre repositorios, demo verde | A3 | ✅ | c905390 | demo exit 0 en el informe |
| F1-07 | código muerto, H16 H17 H18 H19 | A3 | ✅ | c905390 | tests de ciclo y mobile; H19 en el cierre |
| F1-08 | Jinja2 autoescape | A3 | ✅ | c905390 | `test_temas_mapean_rubros_y_no_filtran_el_id` |
| F1-09 | high-value solo en rubros plausibles | A3 | ✅ | c905390 | `test_alto_valor_forzado_solo_en_demo_y_rubro` |
| F1-10 | tests y cobertura ≥ 80 % | A1 A3 A4 | ✅ | e0868d6 | 271 passed, 86.15 % |
| F1-11 | CI | A9 | ✅ | 84a1202 | sin job Docker; el sitio ahora corre `npm test` |
| F1-12 | READMEs | A10 | ✅ | 4ae5920 | README de raíz y de `apps/web` reescritos en el cierre |
| F2-01 | FastAPI health, CORS, errores | A2 | ✅ | f96f839 | `test_health_y_ready` |
| F2-02 | auth admin | A2 | ✅ | 80f5188 | `test_login_cookie_y_csrf` |
| F2-03 | endpoints admin y SSE | A2 | ✅ | f96f839 | `test_sse_emite_y_cierra` |
| F2-04 | export-openapi | A2 | ✅ | f96f839 | `test_openapi_tiene_los_paths_de_f0` |
| F2-05 | dashboard conectado | A6 | ✅ | 4a17816 | 5 tests de Vitest |
| F2-06 | ingresos, HITL, kill switch, costos | A6 | ✅ | 4a17816 | `test_metrics_salen_de_la_base` |
| F2-07 | vistas nuevas | A6 | ✅ | 4a17816 | rutas en `apps/web/README.md` |
| F3-01 | cliente LLM | A3 | ✅ | d09f330 | fallback `sin_key` en el demo |
| F3-02 | Scout Places + demo | A3 | ✅ | c905390 | demo Scout 3 |
| F3-03 | auditor web | A3 | ✅ | c905390 | `test_auditor_no_adivina_email_y_respeta_robots` |
| F3-04 | Diagnoser JSON | A3 | ✅ | c905390 | suite de agentes dentro de los 271 |
| F3-05 | Builder temas | A3 | ✅ | c905390 | `test_temas_mapean_rubros_y_no_filtran_el_id` |
| F3-06 | Filmer | A3 | ✅ | c905390 | storyboard si no hay Chromium ni FFmpeg |
| F3-07 | Checker v2 | A3 A8 | ✅ | d65f02f | `test_compliance.py` |
| F3-08 | Pitcher v2 | A3 A5 | ✅ | ec40161 | `test_frio_no_se_envia` |
| F3-09 | Mobile v2 | A3 | ✅ | c905390 | `test_mobile_solo_loguea_un_mensaje_nuevo` |
| F3-10 | Closer, Delivery, Reporter | A3 | ✅ | c905390 | cobertura individual baja; el total pasa |
| F3-11 | prompts v2 | A3 | ✅ | c905390 | `prompts/` |
| F4-01 | sitio Astro | A7 | ✅ | 68dc531 | build 32 páginas, 5 tests |
| F4-02 | diagnóstico gratis | A7 A2 | ✅ | e0868d6 | e2e de venta, 3 passed |
| F4-03 | checkout MP | A5 A2 A7 | ✅ | e0868d6 | pago falso, sin cobro |
| F4-04 | webhooks agenda | A5 A2 | ✅ | e0868d6 | firma Cal.com en el e2e |
| F4-05 | portal cliente | A7 A2 | ✅ | e0868d6 | intake, vista previa, aprobar |
| F4-06 | deploy Caddy | A5 A9 | ⛔ | ae2635e | Caddyfile presente; sin `docker` local |
| F5-01 | worker jobs | A4 | ✅ | ea42023 | suite del worker |
| F5-02 | cuotas y feriados | A4 | ✅ | ea42023 | `test_worker_jobs.py` |
| F5-03 | cadencias | A4 | ✅ | ea42023 | simulación 14 días |
| F5-04 | guardias HITL | A4 | ✅ | ea42023 | `deal_alto_valor=1` en el reporte |
| F5-05 | reintentos y dead-letter | A4 | ✅ | ea42023 | suite del worker |
| F5-06 | simulación 14 días | A4 | ✅ | ea42023 | `violaciones: 0`, `SIM=0` |
| F6-01 | threat model | A8 | ✅ | e0868d6 | `docs/security/THREAT_MODEL.md` |
| F6-02 | firmas de webhooks | A2 A5 | ✅ | f96f839 | `test_webhook_firma_invalida_es_401` |
| F6-03 | rate limit, honeypot, Turnstile | A2 A7 | ✅ | f96f839 | tests de diagnóstico |
| F6-04 | headers de seguridad | A2 A7 A9 | ✅ | e0868d6 | middleware y Caddyfile |
| F6-05 | secretos y audit | A9 | ✅ | e0868d6 | `test_el_arbol_no_contiene_secretos`; pip-audit y npm prod en 0 |
| F6-06 | tests de prompt-injection | A8 A9 | ✅ | 6958266 | `test_looks_like_injection_cubre_los_cuatro_intentos` |
| F7-01 | Dockerfiles | A9 | ✅ | ae2635e | `infra/Dockerfile.engine` |
| F7-02 | Compose y Caddyfile | A9 | ⛔ | ae2635e | archivos presentes; healthz sin evidencia |
| F7-03 | backups | A9 | ✅ | ae2635e | scripts en `infra/` |
| F7-04 | RUNBOOK | A10 | ✅ | e0868d6 | `docs/RUNBOOK.md` |
| F7-05 | GO_LIVE e INFORME_FINAL | A10 A0 | ✅ | e0868d6 | ambos archivos |
| H1 | read_json no traga JSON inválido | A1 | ✅ | fc72ffb | `test_json_invalido_no_se_reescribe` |
| H2 | load_leads no descarta en silencio | A1 | ✅ | fc72ffb | `test_load_leads_reporta_filas_invalidas` |
| H3 | escritura atómica o vía BD | A1 | ✅ | fc72ffb | `migrate-json` idempotente |
| H4 | transition() aplicada | A1 | ✅ | 8ed6259 | `test_no_hay_asignacion_de_status_fuera_de_core_y_agents` |
| H5 | revision no salta al Checker | A1 A6 | ✅ | f96f839 | `test_aprobar_hitl_vuelve_a_paused_from` |
| H6 | umbrales desde config | A1 | ✅ | 8ed6259 | `response_rate_guard`; constante muerta retirada |
| H7 | HTML con autoescape | A3 | ✅ | c905390 | `test_temas_mapean_rubros_y_no_filtran_el_id` |
| H8 | sin testimonio inventado | A3 | ✅ | d65f02f | `test_rechaza_testimonio_inventado` |
| H9 | link de agenda desde config | A1 A3 | ✅ | c905390 | `booking_link` de configuración |
| H10 | sin Lead ID en la landing | A3 | ✅ | c905390 | el test de temas |
| H11 | LLM real con fallback | A3 | ✅ | d09f330 | log `sin_key` del demo |
| H12 | high-value no forzado en cualquier rubro | A3 | ✅ | c905390 | `test_alto_valor_forzado_solo_en_demo_y_rubro` |
| H13 | un canal, secuencia, sin DM auto | A3 A5 | ✅ | ec40161 | `test_frio_no_se_envia` |
| H14 | Checker por mensaje | A3 A8 | ✅ | d65f02f | `test_compliance.py` |
| H15 | sin HITL duplicado ni imports en loop | A3 | ✅ | c905390 | ciclo único |
| H16 | el ciclo no crea leads demo infinitos | A3 A4 | ✅ | c905390 | `test_run_cycle_no_crea_leads_y_respeta_cuota` |
| H17 | mobile no inunda logs | A3 | ✅ | c905390 | `test_mobile_solo_loguea_un_mensaje_nuevo` |
| H18 | events sin tope ciego | A1 | ✅ | fc72ffb | eventos en la base |
| H19 | cola usada o retirada | A4 | ✅ | e0868d6 | `test_la_cola_json_no_se_crea` |
| H20 | modelos vigentes y alias de API key | A1 | ✅ | 8ed6259 | `LLM_MODEL=grok-4.7` |
| H21 | ingresos solo desde payments | A6 | ✅ | 4a17816 | `test_metrics_salen_de_la_base` |
| H22 | aprobar HITL vuelve a paused_from | A6 | ✅ | 4a17816 | `test_aprobar_hitl_vuelve_a_paused_from` |
| H23 | pitches no se declaran chequeados | A6 | ✅ | f96f839 | `test_editar_deja_el_mensaje_en_checking` |
| H24 | dashboard sin mock de producción | A6 | ✅ | 4a17816 | `mock.ts` solo en un test |
| H25 | kill switch real | A6 A2 | ✅ | f96f839 | `test_kill_switch_persiste_y_app_mode_es_de_solo_lectura` |
| H26 | costo y tokens desde llm_calls | A6 | ✅ | 4a17816 | `test_metrics_salen_de_la_base` |
| H27 | auth admin | A2 A6 | ✅ | 80f5188 | `test_login_cookie_y_csrf` |
| H28 | README sin ruta personal | A10 | ✅ | 4ae5920 | 0 coincidencias de T14 Gen 2 |
| H29 | README real de apps/web | A10 | ✅ | e0868d6 | `apps/web/README.md` |
| H30 | tests, CI, linters, Docker | A9 | ⛔ | 84a1202 | tests y CI verdes; el binario docker falta |

## Bloqueos y cómo se resolvieron

`docker` no está en el PATH. No se inventó un healthz. El resto de la DoD tiene salida en el informe.

La marca de alto valor del demo de partida era un bug de presentación: la columna HV ahora depende solo de `high_value`.

`diagnosticado → agendado` no existía y el recorrido F4 no podía reservar. ADR-012 agrega ese arco cuando el webhook de agenda trae firma y `lead_id`.

## Próxima acción exacta

Instalar Docker, correr `docker compose -f infra/docker-compose.yml up -d --build` y pegar el `healthz`. El PR ya está abierto: https://github.com/datanalytics86/Agente-IA-Autonomo/pull/2.
