#!/usr/bin/env bash
# Falla si el .env enciende outreach o apaga dry-run sin ALLOW_LIVE=true.
# Normaliza comillas, espacios, export y mayúsculas.
# Uso: ALLOW_LIVE=false deploy-guard.sh /ruta/.env
set -euo pipefail

file="${1:?falta el .env}"
allow="${ALLOW_LIVE:-false}"

if [ ! -f "$file" ]; then
  echo "no existe el .env: $file" >&2
  exit 1
fi

is_on() {
  case "$1" in
    true|1|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

allow_norm="$(printf '%s' "$allow" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
if is_on "$allow_norm"; then
  exit 0
fi

value_of() {
  local key="$1" line val found=0 first last
  val=""
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"
    line="$(printf '%s' "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    line="${line#export }"
    line="$(printf '%s' "$line" | sed 's/^[[:space:]]*//')"
    case "$line" in
      "${key}"=*)
        val="${line#*=}"
        val="$(printf '%s' "$val" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
        if [ "${#val}" -ge 2 ]; then
          first="${val%"${val#?}"}"
          last="${val#"${val%?}"}"
          if [ "$first" = "$last" ] && { [ "$first" = '"' ] || [ "$first" = "'" ]; }; then
            val="${val:1:$((${#val} - 2))}"
          fi
        fi
        val="$(printf '%s' "$val" | tr '[:upper:]' '[:lower:]')"
        found=1
        ;;
    esac
  done < "$file"
  if [ "$found" -eq 0 ]; then
    printf '%s' "__missing__"
  else
    printf '%s' "$val"
  fi
}

dry="$(value_of DRY_RUN)"
if ! is_on "$dry"; then
  echo "DRY_RUN=${dry} sin ALLOW_LIVE" >&2
  exit 1
fi

out="$(value_of OUTREACH_ENABLED)"
if is_on "$out"; then
  echo "OUTREACH_ENABLED=${out} sin ALLOW_LIVE" >&2
  exit 1
fi
