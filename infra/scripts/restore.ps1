# Restaura un dump custom en una base temporal y la borra.
# Uso: .\restore.ps1 -Dump .\backups\agencia-....dump
# Exige psql y pg_restore en el PATH. No toca la base de trabajo.

param(
    [Parameter(Mandatory = $true)]
    [string]$Dump
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Dump)) {
    throw "no existe: $Dump"
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
$tmpdb = "restore_$stamp"

function Invoke-Psql([string]$Database, [string]$Sql) {
    & psql --dbname="$Database" -v ON_ERROR_STOP=1 -c $Sql
    if ($LASTEXITCODE -ne 0) {
        throw "psql salió $LASTEXITCODE"
    }
}

try {
    Invoke-Psql "postgres" "DROP DATABASE IF EXISTS $tmpdb"
    Invoke-Psql "postgres" "CREATE DATABASE $tmpdb"
    & pg_restore --no-owner --dbname="$tmpdb" $Dump
    if ($LASTEXITCODE -gt 1) {
        throw "pg_restore salió $LASTEXITCODE"
    }
    Invoke-Psql $tmpdb "SELECT version_num FROM alembic_version"
    Write-Output "restauracion ok: $tmpdb"
}
finally {
    & psql --dbname="postgres" -c "DROP DATABASE IF EXISTS $tmpdb" | Out-Null
}
