# Runbook

Operación local y de producción. Los defaults dejan el sistema en demo: no envía, no cobra y no abre Instagram ni LinkedIn.

## Arranque en demo

PowerShell, desde la raíz del repositorio:

```powershell
cd engine
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe main.py --mode demo
.\.venv\Scripts\python.exe main.py --mode status
```

Bash:

```bash
cd engine
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python main.py --mode demo
.venv/bin/python main.py --mode status
```

`SECRET_KEY` vacío en demo usa un valor efímero del proceso. No se imprime la clave.

## API y admin

```powershell
$env:ADMIN_EMAIL = "admin@example.com"
$env:ADMIN_PASSWORD = "<definir en el entorno, no en el repo>"
.\.venv\Scripts\python.exe main.py --mode create-admin
$env:API_HOST = "127.0.0.1"
$env:API_PORT = "8000"
.\.venv\Scripts\python.exe main.py --mode api
```

`GET /healthz` responde `{"status":"ok"}`. El login es `POST /api/auth/login`. La cookie de sesión es HttpOnly. Las escrituras llevan `X-CSRF-Token`.

## Worker

Un solo proceso. El lock vive en la base.

```powershell
.\.venv\Scripts\python.exe main.py --mode worker
```

Si el kill switch está en falso (default), el worker no envía. Para armar outreach hacen falta las tres condiciones: `APP_MODE=prod`, `OUTREACH_ENABLED=true` y `settings_kv.kill_switch=true`, más la credencial del canal.

## Simulación

No usa red. La misma semilla y los mismos días reescriben el mismo reporte.

```powershell
.\.venv\Scripts\python.exe main.py --mode simulate --days 14 --seed 42
```

El reporte queda en `docs/simulacion/reporte_seed42_d14.md`. En CI corre `--days 3`.

## Sitio y dashboard

```powershell
cd apps\site
npm ci
npm run build
npm test
cd ..\web
npm ci
npm run lint
npm test
npm run build
npm run e2e
```

El e2e levanta la API en `127.0.0.1:8765` y el sitio en `127.0.0.1:4321`, con base sqlite desechable. No cobra: el checkout falso dice que no hubo cobro y el webhook local marca el pago.

## Base de datos

SQLite por defecto: `engine/state/agencia.db` (no se versiona). Postgres 16 en Compose.

```powershell
.\.venv\Scripts\python.exe main.py --mode migrate-json
```

Ese modo copia el JSON legado, no lo reescribe, y se puede correr dos veces. Un JSON corrupto sale con código 1 y no crea la base.

Copia de seguridad: `infra/scripts/backup.ps1` o `backup.sh`. Conservan 14 archivos. Restaurar es reemplazar el archivo sqlite o el dump de Postgres y volver a levantar la API. Probar el restore en una copia, no sobre la base que está en uso.

## Cuando algo sale mal

| Síntoma | Qué mirar |
|---|---|
| No salen correos | Esperado si falta cualquiera de las tres llaves del candado o la credencial. Instagram, LinkedIn y WhatsApp frío quedan en cola manual. |
| Login 429 | Cinco intentos fallidos en 15 minutos. Esperar o reiniciar el proceso en demo. |
| Webhook 401 | Firma o secreto. Mercado Pago no confía en el cuerpo: consulta el pago. |
| `/demo/<token>` 410 | La pieza venció. |
| Dos workers | El segundo no toma el lock. Dejar uno. |
| Alto valor en revisión | Umbral 2.800.000 CLP o rubro forzado en demo. No se envía solo. |

## Producción

Seguir `docs/GO_LIVE.md`. No completar nombre, RUT ni dirección en el código: van por entorno cuando el dueño los tenga. No hay envíos reales ni cobros reales en este runbook.
