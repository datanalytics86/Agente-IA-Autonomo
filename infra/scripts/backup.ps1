# Restauración se prueba en F7. Este script no restaura.
# No lo ejecutes contra una base real antes de esa prueba.
# pg_dump (formato custom) y rotación de 14 archivos.
# DATABASE_URL tiene que ser un URI de libpq (postgresql://...), no el de SQLAlchemy.
# Si no hay DATABASE_URL, usa PGHOST, PGPORT, PGUSER y PGDATABASE.
# No hay secretos en este archivo.

param(
    [string]$Dest = $(if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { ".\backups" })
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$out = Join-Path $Dest "agencia-$stamp.dump"

if ($env:DATABASE_URL) {
    & pg_dump --format=custom --file="$out" --dbname="$env:DATABASE_URL"
} else {
    $pgHost = if ($env:PGHOST) { $env:PGHOST } else { "localhost" }
    $pgPort = if ($env:PGPORT) { $env:PGPORT } else { "5432" }
    $pgUser = if ($env:PGUSER) { $env:PGUSER } else { "agencia" }
    $pgDb = if ($env:PGDATABASE) { $env:PGDATABASE } else { "agencia" }
    & pg_dump --format=custom --file="$out" --host="$pgHost" --port="$pgPort" --username="$pgUser" --dbname="$pgDb"
}
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump falló con código $LASTEXITCODE"
}

$dumps = Get-ChildItem -Path $Dest -Filter "agencia-*.dump" | Sort-Object LastWriteTime -Descending
if ($dumps.Count -gt 14) {
    $dumps | Select-Object -Skip 14 | Remove-Item -Force
}
