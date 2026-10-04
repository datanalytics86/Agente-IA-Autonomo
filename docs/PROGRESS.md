# PROGRESS — Autonomía 04-10-2026

Rama: `grok/autonomia-041026` · Última actualización: 2026-10-04 16:30 America/Santiago · Ola actual: 1

## Estado de la DoD

A ☐ · B ☐ · C ☐ · D ☐ · E ☐ · F ☐ · G ☐

## Línea base F0-02 (commit de partida `19b678b`, Python 3.12.10, Node 22.23.2)

Comando: `engine\.venv\Scripts\python.exe main.py --mode demo` (exit 0).

- Leads: `enviado` 2, `revision` 1, total 3.
- High-value: Gimnasio boutique Santa Lucía, Ñuñoa, 2.932.741 CLP, status `revision`.
- Resumen del propio comando: Scout 3, Diagnoser 3, Builder 3, Filmer 3, Checker 3, Pitcher 2.
- Artefactos en disco: 3 HTML y 3 `storyboard_*.md`.
- `python main.py --mode status` repitió la misma tabla (exit 0).
- `python main.py --mode prompts` listó 8 prompts (exit 0) después del gancho de modos nuevos.

Web, en `apps/web`:

- `npm.cmd ci` exit 0 (152 paquetes). Aviso previo: 1 vulnerabilidad high. La cierra A9 en F6-05, sin tocarla en la línea base.
- `npm.cmd run lint` exit 0: 0 errores, 7 warnings `react(only-export-components)` en `src/routes/**`.
- `npm.cmd run build` exit 0 (`tsc -b && vite build`, 7.11 s).

## Tablero

| ID | Tarea | Agente | Estado | Commit | Evidencia |
|----|-------|--------|--------|--------|-----------|
| F0-01 | Crear rama desde main | A0 | ✅ | | `grok/autonomia-041026` en `19b678b` |
| F0-02 | Línea base §2.2 | A0 | ✅ | | tablas de esta sección |
| F0-03 | Contratos §6.3 | A0 | ✅ | | `docs/contracts/` |
| F0-04 | Tablero | A0 | ✅ | | este archivo |
| F0-05 | DECISIONES y GO_LIVE | A0 | ✅ | | `docs/DECISIONES.md`, `docs/GO_LIVE.md` |
| F1-01 | pyproject + requirements | A1 | ☐ | | |
| F1-02 | core/config.py | A1 | ☐ | | H6 H9 H20 |
| F1-03 | modelos, Alembic, repos | A1 | ☐ | | |
| F1-04 | transition() única | A1 | ☐ | | H4 H5 |
| F1-05 | migrate-json | A1 | ☐ | | H1 H2 H3 |
| F1-06 | agentes sobre repositorios, demo verde | A3 | ☐ | | |
| F1-07 | código muerto, H16 H17 H18 H19 | A3 | ☐ | | |
| F1-08 | Jinja2 autoescape | A3 | ☐ | | H7 H8 H9 H10 |
| F1-09 | high-value solo en rubros plausibles | A3 | ☐ | | H12 |
| F1-10 | tests y cobertura ≥ 80 % | A1 A3 A4 | ☐ | | |
| F1-11 | CI | A9 | ☐ | | |
| F1-12 | READMEs | A10 | ☐ | | H28 H29 |
| F2-01 | FastAPI health, CORS, errores | A2 | ☐ | | |
| F2-02 | auth admin | A2 | ☐ | | H27 |
| F2-03 | endpoints admin y SSE | A2 | ☐ | | |
| F2-04 | export-openapi | A2 | ☐ | | |
| F2-05 | dashboard conectado | A6 | ☐ | | H24 |
| F2-06 | ingresos, HITL, kill switch, costos | A6 | ☐ | | H21 H22 H23 H25 H26 |
| F2-07 | vistas nuevas | A6 | ☐ | | |
| F3-01 | cliente LLM | A3 | ☐ | | H11 |
| F3-02 | Scout Places + demo | A3 | ☐ | | |
| F3-03 | auditor web | A3 | ☐ | | |
| F3-04 | Diagnoser JSON | A3 | ☐ | | |
| F3-05 | Builder temas | A3 | ☐ | | |
| F3-06 | Filmer | A3 | ☐ | | |
| F3-07 | Checker v2 | A3 A8 | ☐ | | H14 |
| F3-08 | Pitcher v2 | A3 A5 | ☐ | | H13 |
| F3-09 | Mobile v2 | A3 | ☐ | | |
| F3-10 | Closer, Delivery, Reporter | A3 | ☐ | | |
| F3-11 | prompts v2 | A3 | ☐ | | |
| F4-01 | sitio Astro | A7 | ☐ | | |
| F4-02 | diagnóstico gratis | A7 A2 | ☐ | | |
| F4-03 | checkout MP | A5 A2 A7 | ☐ | | |
| F4-04 | webhooks agenda | A5 A2 | ☐ | | |
| F4-05 | portal cliente | A7 A2 | ☐ | | |
| F4-06 | deploy Caddy | A5 A9 | ☐ | | |
| F5-01 | worker jobs | A4 | ☐ | | |
| F5-02 | cuotas y feriados | A4 | ☐ | | |
| F5-03 | cadencias | A4 | ☐ | | |
| F5-04 | guardias HITL | A4 | ☐ | | |
| F5-05 | reintentos y dead-letter | A4 | ☐ | | |
| F5-06 | simulación 14 días | A4 | ☐ | | |
| F6-01 | threat model | A8 | ☐ | | |
| F6-02 | firmas de webhooks | A2 A5 | ☐ | | |
| F6-03 | rate limit, honeypot, Turnstile | A2 A7 | ☐ | | |
| F6-04 | headers de seguridad | A2 A7 A9 | ☐ | | |
| F6-05 | secretos y audit | A9 | ☐ | | |
| F6-06 | tests de prompt-injection | A8 A9 | ☐ | | |
| F7-01 | Dockerfiles | A9 | ☐ | | |
| F7-02 | Compose y Caddyfile | A9 | ☐ | | |
| F7-03 | backups | A9 | ☐ | | |
| F7-04 | RUNBOOK | A10 | ☐ | | |
| F7-05 | GO_LIVE e INFORME_FINAL | A10 A0 | ☐ | | |
| H1 | read_json no traga JSON inválido | A1 | ☐ | | F1-05 |
| H2 | load_leads no descarta en silencio | A1 | ☐ | | F1-05 |
| H3 | escritura atómica o vía BD | A1 | ☐ | | F1-05 |
| H4 | transition() aplicada | A1 | ☐ | | F1-04 |
| H5 | revision no salta al Checker | A1 A6 | ☐ | | F1-04 F2-06 |
| H6 | umbrales desde config | A1 | ☐ | | F1-02 |
| H7 | HTML con autoescape | A3 | ☐ | | F1-08 |
| H8 | sin testimonio inventado | A3 | ☐ | | F1-08 |
| H9 | link de agenda desde config | A1 A3 | ☐ | | F1-02 F1-08 |
| H10 | sin Lead ID en la landing | A3 | ☐ | | F1-08 |
| H11 | LLM real con fallback | A3 | ☐ | | F3-01 |
| H12 | high-value no forzado en cualquier rubro | A3 | ☐ | | F1-09 |
| H13 | un canal, secuencia, sin DM auto | A3 A5 | ☐ | | F3-08 |
| H14 | Checker por mensaje | A3 A8 | ☐ | | F3-07 |
| H15 | sin HITL duplicado ni imports en loop | A3 | ☐ | | F1-07 |
| H16 | el ciclo no crea leads demo infinitos | A3 A4 | ☐ | | F1-07 |
| H17 | mobile no inunda logs | A3 | ☐ | | F1-07 |
| H18 | events sin tope ciego | A1 | ☐ | | F1-03 |
| H19 | cola usada o retirada | A4 | ☐ | | F5-01 |
| H20 | modelos vigentes y alias de API key | A1 | ☐ | | F1-02 |
| H21 | ingresos solo desde payments | A6 | ☐ | | F2-06 |
| H22 | aprobar HITL vuelve a paused_from | A6 | ☐ | | F2-06 |
| H23 | pitches no se declaran chequeados | A6 | ☐ | | F2-06 |
| H24 | dashboard sin mock de producción | A6 | ☐ | | F2-05 |
| H25 | kill switch real | A6 A2 | ☐ | | F2-06 |
| H26 | costo y tokens desde llm_calls | A6 | ☐ | | F2-06 |
| H27 | auth admin | A2 A6 | ☐ | | F2-02 |
| H28 | README sin ruta personal | A10 | ☐ | | F1-12 |
| H29 | README real de apps/web | A10 | ☐ | | F1-12 |
| H30 | tests, CI, linters, Docker | A9 | ☐ | | F1-11 F7 |

## Bloqueos y cómo se resolvieron

Ninguno. La spec vivía solo en `claude/ecstatic-mayer-8tna8e` (`0dfe69e`). La rama de trabajo sale de `main` (`19b678b`) y el archivo entra en el primer commit de esta rama.

## Próxima acción exacta

Ola 1 en paralelo: A1 núcleo y BD, A8 compliance, A9 harness y CI, A10 READMEs. Al cerrar, suite de lo que ya exista y rebase a esta rama.
