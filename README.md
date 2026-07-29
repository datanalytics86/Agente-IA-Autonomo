# Agente IA Autónomo

Monorepo de agencia unipersonal: **motor multiagente (Python)** + **dashboard (React)** para vender **landing pages a pymes locales en Chile**.

Modo **DEMO** sin APIs obligatorias. Estado del motor en filesystem JSON.

## Estructura

```
Agente-IA-Autonomo/
├── apps/web/                 # Dashboard React (capa 1)
├── engine/                   # Motor multiagente Python (capa 2)
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── prompts/              # 8 prompts (orchestrator + 7 agentes)
│   ├── agents/               # base, scout, diagnoser, builder, filmer,
│   │                         # checker, pitcher, mobile, pipeline
│   ├── state/                # leads.json, logs.json, queue.json
│   └── output/               # landings HTML + storyboards
├── README.md
└── .gitignore
```

## Flujo de negocio

1. Encontrar negocios sin web o con web desactualizada  
2. Diagnosticar la oportunidad  
3. Crear landing HTML  
4. Storyboard / video vertical 10–15s  
5. Pitch en español chileno  
6. Compliance (Ley 21.719 + anti-spam + opt-out STOP)  
7. Envío simulado (IG DM, email, LinkedIn; WhatsApp no cold agresivo)  
8. Responder leads y agendar  

**Human-in-the-loop** si deal ≥ **2.800.000 CLP** (~3.000 USD) o tasa de respuesta &lt; 12%.

| Agente | Rol |
|--------|-----|
| Orchestrator | Coordina, prioriza, HITL, logs |
| Scout | Leads demo (prod: Google Places) |
| Diagnoser | Diagnóstico + pitch ES-CL |
| Builder | Landing HTML (5 secciones) |
| Filmer | Storyboard / video |
| Checker | Calidad + Ley 21.719 |
| Pitcher | Envía solo si Checker aprueba |
| Mobile | Respuestas cortas + Calendly |

**Status del lead:**  
`nuevo` → `diagnosticado` → `landing` → `video` → `pitch_listo` → `enviado` → `respondio` → `agendado` → `cerrado`  
Alternativa: `revision` (HITL)

---

## Capa 2 — Motor Python

### Requisitos

- Python **3.11+**

### Instalación

```powershell
cd "C:\Users\T14 Gen 2\Agente-IA-Autonomo\engine"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Comandos

```powershell
python main.py --mode demo      # ciclo completo demo
python main.py --mode status    # tabla + logs
python main.py --mode scout     # solo Scout
python main.py --mode cycle     # un ciclo sobre estado
python main.py --mode prompts   # lista prompts/
```

Desde la raíz del monorepo:

```powershell
python engine/main.py --mode demo
python engine/main.py --mode status
```

### Resultado esperado del demo

- `engine/state/leads.json` con leads chilenos  
- `engine/state/logs.json` con actividad  
- `engine/output/*.html` landings  
- Al menos un lead **high-value** en `revision` (sin envío automático)

Variables opcionales: copiar `engine/.env.example` → `engine/.env`.

---

## Capa 1 — Dashboard React

### Stack

React 19 · TypeScript · Vite · TanStack Router (file routes) · Tailwind CSS v4 · Zustand · Recharts · Lucide · Sonner

### Rutas

| Ruta | Contenido |
|------|-----------|
| `/` | Panel: KPIs, acciones, gráfico, logs, agentes |
| `/agentes` | 8 agentes + flujo + prompt orchestrator |
| `/leads` | Pipeline con filtros + Avanzar/Aprobar/Descartar |
| `/logs` | Historial de eventos |
| `/config` | Precios CLP, Ley 21.719, ciudades, stack |

### Instalación y arranque

```powershell
cd "C:\Users\T14 Gen 2\Agente-IA-Autonomo\apps\web"
npm install
npm run dev
```

Abre **http://localhost:8080** (escucha en `0.0.0.0:8080`).

```powershell
npm run build    # producción
npm run preview  # servir build en :8080
```

### Acciones del store (demo)

- **Correr Scout** — agrega 3–5 leads chilenos  
- **Enviar pitches** — `pitch_listo` → `enviado`  
- **Revisar deals** — filtra `revision` (HITL)  
- **Aprobar / Descartar** en leads de revisión  

Los datos del dashboard son **mock en Zustand** (independientes del JSON del engine, misma semántica de status/agentes).

---

## Reglas de negocio (ambas capas)

- Precio paquete: **250k–450k CLP**  
- Escalamiento humano: deal &gt; ~3.000 USD / 2.8M CLP  
- Canales: IG DM, email, LinkedIn; WhatsApp sin cold agresivo  
- Opt-out claro; no inventar teléfonos/emails no públicos  

## Extender a producción

1. Completar `engine/.env` con APIs reales  
2. Conectar Google Places en Scout  
3. Activar LLM en Diagnoser/Pitcher  
4. Integrar envíos reales con consentimientos  
5. Opcional: API que lea/escriba el mismo `engine/state` desde el dashboard  

## Licencia de uso

Proyecto demo de arquitectura multiagente. Revisar compliance y términos de cada canal antes de envíos reales.
