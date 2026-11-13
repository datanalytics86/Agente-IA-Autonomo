#!/usr/bin/env bash
# pg_dump (formato custom) y rotación de 14 archivos.
# Si ENGINE_OUTPUT_DIR es un directorio, archiva ese árbol (volumen engine_output).
# DATABASE_URL tiene que ser un URI de libpq (postgresql://...), no el de SQLAlchemy.
# Si no hay DATABASE_URL, usa PGHOST, PGPORT, PGUSER y PGDATABASE.
# Este script no restaura.

set -euo pipefail

dest="${1:-${BACKUP_DIR:-./backups}}"
mkdir -p "$dest"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${dest}/agencia-${stamp}.dump"

if [[ -n "${DATABASE_URL:-}" ]]; then
  pg_dump --format=custom --file="$out" --dbname="$DATABASE_URL"
else
  pg_dump --format=custom --file="$out" \
    --host="${PGHOST:-localhost}" \
    --port="${PGPORT:-5432}" \
    --username="${PGUSER:-agencia}" \
    --dbname="${PGDATABASE:-agencia}"
fi

rotate() {
  local pattern="$1"
  shopt -s nullglob
  local files=("${dest}"/${pattern})
  if ((${#files[@]} > 14)); then
    mapfile -t sorted < <(ls -1t "${dest}"/${pattern})
    local old
    for old in "${sorted[@]:14}"; do
      rm -f -- "$old"
    done
  fi
}

rotate "agencia-*.dump"

output_dir="${ENGINE_OUTPUT_DIR:-}"
if [[ -n "$output_dir" && -d "$output_dir" ]]; then
  tar -C "$output_dir" -cf "${dest}/agencia-${stamp}-output.tar" .
  rotate "agencia-*-output.tar"
fi
