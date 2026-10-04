# Cambios de contrato

Nadie edita `dominio.md`, `db.md`, `openapi.yaml`, `env.md` ni `integraciones.md` salvo A0.

Para proponer un cambio, agrega una fila y espera el merge de A0.

| Fecha | Autor | Contrato | Propuesta | Estado |
|---|---|---|---|---|
| 2026-10-04 | A0 | db.md | Tablas `webhook_events` y `worker_lock`, y status `blocked` en `messages`, porque el mínimo no alcanzaba para idempotencia, lock y triple candado | aprobado |
| 2026-10-04 | A0 | dominio.md | 15 slugs ASCII únicos (los slugs históricos se repetían) y `engine/main.py` solo lo edita A0 | aprobado |
