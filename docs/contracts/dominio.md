# Contrato de dominio

Fuente: `instrucciones041026.md` §8.2, §8.4 y §3.2. Si este archivo y el código divergen, manda este contrato hasta que A0 registre el cambio en `CAMBIOS.md`.

Identificadores en inglés. Valores de estado y textos de negocio en español.

## Estados

Prospección: `nuevo`, `diagnosticado`, `landing`, `video`, `pitch_listo`, `enviado`, `respondio`, `agendado`.

Venta y entrega: `propuesta`, `pagado`, `en_produccion`, `en_revision_cliente`, `entregado`, `postventa`.

Laterales: `revision` (guarda `paused_from`), `perdido` (exige `close_reason`), `opt_out`.

`cerrado` es legado y no se escribe en código nuevo. Migración JSON:

| Motivo en el JSON | Estado destino |
|---|---|
| contiene «no interesado» o es opt-out | `opt_out` |
| «Descartado» o `reject` | `perdido` (`close_reason=descartado`) |
| cualquier otro `cerrado` | `perdido` (`close_reason=legacy_cerrado`) |

Inbound: diagnóstico gratis entra en `diagnosticado`; contacto entra en `respondio`. Ambos llevan `source` inbound y `consent` completo. Un webhook de agenda firmado puede pasar ese diagnóstico a `agendado` sin recorrer el pitch (ADR-012).

## Transiciones

Única función autorizada a asignar `lead.status`:

```text
transition(lead, to, *, actor, reason) -> Lead
```

`actor` ∈ `agente` | `humano` | `sistema` | `webhook`.

La función valida la arista, escribe `lead_events` y un `events` de nivel `info`, y actualiza `updated_at`. Si la arista no existe, lanza `TransitionError` y no persiste. Desde `revision`, el caller pasa el token `paused_from` (la función lo resuelve al estado guardado) o `perdido` / `opt_out`. Pedir el nombre concreto del estado, por ejemplo `enviado`, se rechaza. Si el mensaje fue editado, el servicio de aprobación lo devuelve a `checking` antes de llamar a `transition`.

| Desde | Hacia |
|---|---|
| nuevo | diagnosticado, revision, perdido, opt_out |
| diagnosticado | landing, agendado, revision, perdido, opt_out |
| landing | video, pitch_listo, revision, perdido, opt_out |
| video | pitch_listo, revision, perdido, opt_out |
| pitch_listo | enviado, revision, perdido, opt_out |
| enviado | respondio, agendado, perdido, revision, opt_out |
| respondio | agendado, propuesta, revision, perdido, opt_out |
| agendado | propuesta, revision, perdido, opt_out |
| propuesta | pagado, revision, perdido, opt_out |
| pagado | en_produccion, revision |
| en_produccion | en_revision_cliente, revision |
| en_revision_cliente | en_produccion, entregado, revision |
| entregado | postventa |
| revision | paused_from, perdido, opt_out |
| perdido | nuevo |
| postventa | — |
| opt_out | — |

Reglas extra:

- `landing → pitch_listo` solo si el video está deshabilitado (`VIDEO_ENABLED=false`).
- `perdido → nuevo` solo con `actor=humano` y si el contacto no está en `suppression`.
- `pitch_listo → enviado` solo si el mensaje está `approved` por el Checker. `revision` nunca va directo a `enviado`.
- Aprobar un HITL vuelve a `paused_from`. Si el mensaje fue editado, su status vuelve a `checking` y debe aprobar el Checker antes de encolarse.
- Un pago ya hecho más un opt-out de marketing suprime canales, y el proyecto sigue su curso.
- Un upsell no cambia el estado del lead: crea otra `order`.

Test de regresión obligatorio: falla si cualquier `.py` bajo `engine/` fuera de `engine/core/` contiene una asignación `.status =` (se permiten tests que construyen fixtures mediante la API de repositorio o `transition`).

## HITL (una sola implementación en `engine/core/`)

| Regla | Efecto |
|---|---|
| `estimated_value_clp >= HITL_VALUE_CLP` (2_800_000) | `revision` antes de cualquier envío o propuesta. `approvals.kind=deal_alto_valor` |
| tasa de respuesta del canal < `HITL_RESPONSE_RATE` (0.12) con muestra ≥ `HITL_MIN_SAMPLE` (30) | pausa ese canal y `approvals.kind=tasa_respuesta_baja`. Umbral configurable por canal en `settings_kv` |
| confianza del clasificador < `MOBILE_AUTOREPLY_MIN_CONFIDENCE` (0.8) | borrador HITL, sin auto-respuesta |
| error de compliance, desacuerdo reglas/juez, fuera de alcance, reembolso | HITL (`compliance`, `fuera_de_alcance` o `error_sistema`) |

`paused_from` conserva el estado previo. Alto valor en demo solo en rubros `clinica-dental`, `optica`, `inmobiliaria`, `abogados` o paquete `multi_sede`.

## Rubros canónicos (15)

Slug único ASCII. El tema Jinja2 es uno de `formal`, `belleza`, `gastronomia`, `servicios`.

| Slug | Etiqueta | Tema | Tono |
|---|---|---|---|
| clinica-dental | Clínica dental | formal | usted |
| optica | Óptica | formal | usted |
| abogados | Estudio de abogados | formal | usted |
| estudio-contable | Estudio contable | formal | usted |
| peluqueria | Peluquería | belleza | tu |
| centro-estetica | Centro de estética | belleza | tu |
| spa | Spa y masajes | belleza | tu |
| gimnasio | Gimnasio boutique | belleza | tu |
| cafeteria | Cafetería | gastronomia | tu |
| restaurante | Restaurante de barrio | gastronomia | tu |
| taller-mecanico | Taller mecánico | servicios | tu |
| inmobiliaria | Inmobiliaria local | servicios | tu |
| veterinaria | Veterinaria | servicios | tu |
| escuela-idiomas | Escuela de idiomas | servicios | tu |
| ferreteria | Ferretería | servicios | tu |

`multi_sede` no es rubro de scout: es paquete siempre HITL.

## Paquetes

| code | CLP | Revisiones | Notas |
|---|---|---|---|
| landing_esencial | 250_000 | 1 | 5 secciones, publicación |
| landing_pro | 350_000 | 2 | esencial + video 12 s + formulario + WhatsApp del cliente |
| landing_premium | 450_000 | 3 | pro + SEO local + schema.org |
| multi_sede | null | — | a cotizar, siempre HITL |

Anticipo `DEPOSIT_PERCENT` (50). Saldo antes de publicar. IVA 19 % según `PRICES_INCLUDE_IVA`. Mantención solo si `MAINTENANCE_PRICE_CLP` tiene valor.

## Agentes

Cada agente es una clase `run(ctx) -> AgentResult`, idempotente, lee y escribe solo por repositorios y cambia estados solo con `transition()`.

`AgentResult` tiene `lead_id`, `ok`, `events` y `output` (dict validado).

El LLM entra por `complete_json(prompt_name, schema, data, model=...)`. Reintenta 2 veces con el error de validación. Registra `llm_calls`. Sin key, sin presupuesto o tras el fallo: fallback al template determinista y evento `warn`.

HTML scrapeado y mensajes entrantes viajan dentro de `<datos_no_confiables>` y no se obedecen.

## Triple candado de envío

Un adaptador de canal envía a la red solo si se cumplen las cuatro:

1. `APP_MODE=prod`
2. `OUTREACH_ENABLED=true`
3. `settings_kv.kill_switch == true` (armada). Default `false` (detenida).
4. Hay credencial de ese canal.

Si falta una, el adaptador persiste el intento como `blocked` y no abre socket. Instagram, LinkedIn y WhatsApp en frío nunca salen del adaptador: quedan en `manual_pending`.

## CLI

`engine/main.py` lo edita solo A0. Los modos históricos `demo`, `status`, `scout`, `cycle`, `prompts` siguen ahí.

Modos nuevos, import perezoso (si el módulo no existe, el modo responde «no implementado» con código 2):

| Modo | Callable |
|---|---|
| migrate-json | `db.migrate_json:main` |
| seed | `db.seed:main` |
| api | `api.cli:main` |
| export-openapi | `api.cli:export_openapi` |
| create-admin | `api.cli:create_admin` |
| worker | `worker.cli:main` |
| simulate | `simulation.cli:main` |

Argumentos de simulate: `--days` (int), `--seed` (int).
