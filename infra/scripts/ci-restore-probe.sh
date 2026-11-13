#!/usr/bin/env bash
# Semilla mínima y restore-check. Pensado para el cliente de Postgres 16.
set -euo pipefail

psql -v ON_ERROR_STOP=1 -c "CREATE TABLE probe (id int primary key, note text);"
psql -v ON_ERROR_STOP=1 -c "INSERT INTO probe (id, note) VALUES (1, 'uno'), (2, 'dos');"
bash infra/scripts/restore-check.sh | tee /tmp/restore.out
grep -qx ok /tmp/restore.out
test "$(psql -At -c 'SELECT count(*) FROM probe')" = "2"
