# Agente IA Autónomo

Monorepo para vender landings a pymes en Chile. Tres piezas:

- `engine/` — motor Python: agentes, API FastAPI, worker y simulación. La base por defecto es SQLite (`engine/state/agencia.db`). En producción el contrato apunta a Postgres.
- `apps/web/` — panel React. Lee la API con cookie de sesión. No inventa leads ni ingresos.
- `apps/site/` — sitio público en Astro: diagnóstico, precios, checkout y portal del cliente.

`infra/` tiene Docker Compose y Caddy. Los contratos están en `docs/contracts/`. La operación está en `docs/RUNBOOK.md` y el checklist del dueño en `docs/GO_LIVE.md`.

Sin credenciales el sistema queda en demo: no envía, no cobra y no manda mensajes directos de Instagram ni de LinkedIn. Esos dos canales quedan en una bandeja para envío manual. El nombre, el RUT y la dirección de la agencia no van en el código: el sitio muestra `[datos de la agencia]` hasta que el dueño los pone en el entorno.

## Modos del motor

Desde `engine/`, con el venv activo:

| Modo | Qué hace |
|------|----------|
| `demo` | Un ciclo con datos sintéticos |
| `status` | Tabla de leads |
| `scout` | Solo el explorador |
| `cycle` | Un ciclo sobre el estado ya guardado |
| `prompts` | Lista `prompts/` |
| `migrate-json` | Copia `leads.json` y `logs.json` a la base. No reescribe el origen. La segunda pasada no duplica |
| `seed` | Semilla de desarrollo |
| `api` | API HTTP |
| `export-openapi` | Vuelca el OpenAPI generado |
| `create-admin` | Crea el usuario del panel. Email y clave salen del entorno |
| `worker` | Jobs. Con el kill switch en falso no envía |
| `simulate` | Reloj falso. `--days` y `--seed` |

## Instalación

Python 3.12 y Node 22. PowerShell, desde la raíz:

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

Panel y sitio:

```powershell
cd apps/web
npm ci
npm run dev
```

```bash
cd apps/web
npm ci
npm run dev
```

El panel abre http://localhost:8080. El sitio, en `apps/site`, usa `npm run dev` de Astro. Para dejar la API arriba hace falta `create-admin` y `--mode api`, como está en el runbook.

## Reglas que el código no cruza

- Precio publicado del paquete: 250.000 a 450.000 CLP. Un deal de 2.800.000 CLP o más, o una tasa de respuesta bajo el umbral configurado, para en revisión humana.
- Outreach real solo con las tres condiciones: `APP_MODE=prod`, `OUTREACH_ENABLED=true` y `settings_kv.kill_switch=true`, más la credencial del canal. El default es demo, dry-run, outreach apagado y kill switch en falso.
- WhatsApp no se usa en frío. Instagram y LinkedIn no se automatizan.
- No hay cobro real en demo. El checkout falso dice que no se hizo ningún cobro.
