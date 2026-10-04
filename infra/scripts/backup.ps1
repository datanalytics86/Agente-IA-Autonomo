# pg_dump (formato custom) y rotación de 14 días.
# DATABASE_URL puede ser el URI de SQLAlchemy (postgresql+psycopg://).
# La restauración está en restore.ps1. No hay secretos en este archivo.

param(
    [string]$Dest = $(if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { ".\backups" })
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$out = Join-Path $Dest "agencia-$stamp.dump"

if ($env:DATABASE_URL) {
    $url = $env:DATABASE_URL -replace '^postgresql\+psycopg2?://', 'postgresql://'
    & pg_dump --format=custom --file="$out" --dbname="$url"
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

$limit = (Get-Date).AddDays(-14)
Get-ChildItem -Path $Dest -Filter "agencia-*.dump" |
    Where-Object { $_.LastWriteTime -lt $limit } |
    Remove-Item -Force

$dumps = Get-ChildItem -Path $Dest -Filter "agencia-*.dump" | Sort-Object LastWriteTime -Descending
if ($dumps.Count -gt 14) {
    $dumps | Select-Object -Skip 14 | Remove-Item -Force
}

Write-Output $out
