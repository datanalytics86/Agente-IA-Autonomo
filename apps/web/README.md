# Dashboard

Panel local del monorepo para seguir el demo de landings a pymes en Chile. No es un sitio público y no habla con el motor: los datos salen de un store Zustand con mocks. Conectar el panel a una API es trabajo posterior; hoy no hay cliente HTTP.

## Stack

Leído de `package.json`:

- React 19 (`react` y `react-dom` ^19.2.7) y TypeScript ~6.0.2
- Vite ^8.1.1 con `@vitejs/plugin-react`
- TanStack Router (`@tanstack/react-router` ^1.170.18), rutas por archivo en `src/routes/`
- Tailwind CSS v4 (`tailwindcss` ^4.3.3 y `@tailwindcss/vite`)
- Zustand ^5.0.14
- Recharts ^3.10.1
- Lucide (`lucide-react`) y toasts Sonner (`sonner`)
- Lint: oxlint (`npm run lint`)

## Rutas

| Ruta | Qué muestra hoy |
|------|-----------------|
| `/` | Panel: KPIs, acciones rápidas, gráfico, logs y agentes |
| `/agentes` | Los 8 agentes, el flujo de status y el prompt del orchestrator |
| `/leads` | Pipeline con filtros; avanzar, aprobar o descartar |
| `/logs` | Historial de eventos del store |
| `/config` | Precios CLP, Ley 21.719, ciudades piloto y stack |

## Datos

Mock de Zustand (`src/store/useAgencyStore.ts`, semillas en `src/lib/mock.ts`). Es independiente de `engine/state/*.json`, con la misma idea de status y de agentes. Las acciones del panel (correr Scout, enviar pitches, revisar deals en `revision`, avanzar, aprobar o descartar) solo mutan ese store.

## Arranque

Desde la raíz del repositorio. `npm ci` instala lo fijado en `package-lock.json`.

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

Abre http://localhost:8080. Vite escucha en `0.0.0.0:8080` (`vite.config.ts`, también en `preview`). `npm run build` compila; `npm run preview` sirve ese build en el mismo puerto.
