#!/usr/bin/env bash
# Comprueba el restore de una base que ya tiene el esquema (alembic) y la semilla.
# El cliente tiene que ser Postgres 16. No crea tablas de prueba.
set -euo pipefail

bash infra/scripts/restore-check.sh | tee /tmp/restore.out
grep -qx ok /tmp/restore.out
test "$(psql -At -c "SELECT value::text FROM settings_kv WHERE key='kill_switch'")" = "false"
