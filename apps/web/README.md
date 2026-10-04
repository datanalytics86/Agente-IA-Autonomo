# Dashboard

Panel de administración. Las cifras salen de la API del motor (`/api/...`) con la cookie de sesión HttpOnly y la cabecera `X-CSRF-Token` en las escrituras. Zustand guarda estado de interfaz. Si la API no responde, el panel no muestra leads, ingresos ni textos inventados.

## Stack

Leído de `package.json`:

- React 19 y TypeScript ~6
- Vite 8
- TanStack Router (rutas por archivo en `src/routes/`) y TanStack Query
- Tailwind CSS v4
- Zustand 5, solo interfaz
- Recharts, Lucide y Sonner
- Lint: oxlint (`npm run lint`)
- Tests: Vitest (`npm test`) y Playwright (`npm run e2e`)

## Rutas

| Ruta | Qué muestra |
|------|-------------|
| `/login` | Ingreso del admin |
| `/` | Panel. Indicadores de `GET /api/metrics` |
| `/agentes` | Agentes y prompts de `GET /api/agents`. Ejecutar encola un job |
| `/leads` | Pipeline |
| `/leads/$leadId` | Detalle, timeline, mensajes y artefactos |
| `/hitl` | Bandeja humana. Aprobar devuelve el lead a la etapa en pausa |
| `/manual` | Instagram y LinkedIn se copian y se marcan enviados a mano |
| `/conversaciones` | Respuesta asistida. Pasa por el Checker |
| `/proyectos` | Entrega y pedidos. El ingreso del mes está en el panel |
| `/logs` | Eventos del motor |
| `/compliance` | Supresión por hash y solicitudes de derechos. Sin el valor en claro |
| `/config` | Ajustes. El kill switch se guarda. El modo demo o prod no se edita aquí |

`src/lib/mock.ts` lo importa un test (`src/api/metrics.test.ts`). Ninguna pantalla lo importa.

## Arranque

La API tiene que estar arriba. Los comandos de `create-admin` y `--mode api` están en `docs/RUNBOOK.md`.

**PowerShell**

```powershell
cd apps/web
npm ci
npm run dev
```

**bash**

```bash
cd apps/web
npm ci
npm run dev
```

Abre http://localhost:8080. Vite escucha en `0.0.0.0:8080`.

En la misma carpeta: `npm run lint`, `npm run build`, `npm test` y `npm run e2e`. El e2e levanta la API en `127.0.0.1:8765` con una base SQLite desechable y el sitio en el puerto 4321. El pago es el falso local: no llama a Mercado Pago y no cobra.
