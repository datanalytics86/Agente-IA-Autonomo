import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/config')({
  component: ConfigPage,
})

function ConfigPage() {
  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Configuración</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Precios CLP, compliance Chile y stack del monorepo
        </p>
      </header>

      <section className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
        <h2 className="text-sm font-semibold">Precios y HITL</h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          <Item k="Paquete landing" v="250.000 – 450.000 CLP" />
          <Item k="Umbral revisión humana" v="≥ 2.800.000 CLP (~3.000 USD)" />
          <Item k="Tasa respuesta crítica" v="< 12% → escalar HITL" />
          <Item k="Pagos sugeridos" v="Transferencia · Mercado Pago · Webpay" />
        </dl>
      </section>

      <section className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
        <h2 className="text-sm font-semibold">Ley 21.719 y canales</h2>
        <ul className="mt-3 space-y-2 text-sm text-zinc-300">
          <li>Opt-out claro en todo pitch (STOP / no más mensajes).</li>
          <li>No inventar teléfonos ni emails no públicos.</li>
          <li>Canales prioritarios: Instagram DM, email, LinkedIn.</li>
          <li>WhatsApp: no cold agresivo; solo con warning / consentimiento.</li>
          <li>Checker aprueba antes de cualquier envío del Pitcher.</li>
        </ul>
      </section>

      <section className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
        <h2 className="text-sm font-semibold">Ciudades piloto</h2>
        <p className="mt-3 text-sm leading-relaxed text-zinc-300">
          Providencia, Las Condes, Ñuñoa, Maipú, Viña del Mar, Valparaíso, Concepción,
          Temuco, La Serena.
        </p>
      </section>

      <section className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
        <h2 className="text-sm font-semibold">Stack</h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          <Item k="Dashboard" v="React 19 · Vite · TanStack Router · Tailwind v4 · Zustand · Recharts · Lucide · Sonner" />
          <Item k="Motor" v="Python 3.11+ · pydantic · rich · filesystem JSON" />
          <Item k="CLI" v="python engine/main.py --mode demo|status|scout|cycle|prompts" />
          <Item k="Web" v="npm run dev → http://0.0.0.0:8080" />
        </dl>
      </section>
    </div>
  )
}

function Item({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-xl border border-white/5 bg-surface/60 p-3">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">{k}</dt>
      <dd className="mt-1 text-sm text-zinc-200">{v}</dd>
    </div>
  )
}
