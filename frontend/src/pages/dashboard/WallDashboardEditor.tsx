import { useState } from 'react'
import {
  DEFAULT_WALL_DASHBOARD,
  WALL_DASHBOARD_WIDGETS,
  wallDashboardWidgetLabel,
  type WallDashboardConfig,
  type WallDashboardPage,
  type WallDashboardWidget,
  type WallDashboardWidgetKey,
} from '../../api/wall'

const btn = 'rounded bg-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-600 disabled:opacity-40'
const field = 'rounded border border-slate-600 bg-slate-900 px-2 py-1 text-sm text-white'
const MAX_PAGES = 6

function moveWidget(widgets: WallDashboardWidget[], from: number, to: number): WallDashboardWidget[] {
  if (from === to || from < 0 || to < 0 || from >= widgets.length || to >= widgets.length) return widgets
  const next = [...widgets]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

function missingWidgets(page: WallDashboardPage): WallDashboardWidgetKey[] {
  const have = new Set(page.widgets.map((w) => w.key))
  return WALL_DASHBOARD_WIDGETS.filter((w) => !have.has(w.key)).map((w) => w.key)
}

export default function WallDashboardEditor({ config, current, onSelect, onChange, saving }: {
  config: WallDashboardConfig; current: number; saving: boolean
  onSelect: (i: number) => void; onChange: (config: WallDashboardConfig) => void
}) {
  const pages = config.pages.length ? config.pages : DEFAULT_WALL_DASHBOARD.pages
  const index = Math.min(current, pages.length - 1)
  const page = pages[index]
  const [adding, setAdding] = useState<WallDashboardWidgetKey | ''>('')
  const [dragFrom, setDragFrom] = useState<number | null>(null)
  const missing = missingWidgets(page)

  const updatePage = (fn: (p: WallDashboardPage) => WallDashboardPage) => onChange({ ...config, pages: pages.map((p, i) => (i === index ? fn(p) : p)) })
  const updateWidgets = (fn: (ws: WallDashboardWidget[]) => WallDashboardWidget[]) => updatePage((p) => ({ ...p, widgets: fn(p.widgets) }))
  const indexOf = (ws: WallDashboardWidget[], key: WallDashboardWidgetKey) => ws.findIndex((w) => w.key === key)
  const move = (key: WallDashboardWidgetKey, by: number) => updateWidgets((ws) => moveWidget(ws, indexOf(ws, key), indexOf(ws, key) + by))

  return (
    <section className="space-y-4 rounded-xl border border-slate-700 bg-slate-900/90 p-4" aria-label="Family wall dashboard">
      <div>
        <h2 className="text-lg font-semibold text-white">Family wall dashboard</h2>
        <p className="text-sm text-slate-400">Shared by the whole family and shown read-only on paired wall displays.</p>
      </div>
      {pages.length > 1 && (
        <div className="flex gap-1 rounded-lg bg-slate-950/70 p-1" role="tablist" aria-label="Wall dashboard pages">
          {pages.map((p, i) => <button key={`${p.name}-${i}`} role="tab" aria-selected={i === index} onClick={() => onSelect(i)}
            className={`rounded px-3 py-1 text-sm ${i === index ? 'bg-primary text-white' : 'text-slate-300 hover:text-white'}`}>{p.name}</button>)}
        </div>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">Wall page name
          <input className={`${field} mt-1 block w-40`} maxLength={40} value={page.name}
            onChange={(e) => updatePage((p) => ({ ...p, name: e.target.value || ' ' }))} />
        </label>
        <label className="text-xs text-slate-400">Wall page duration
          <input className={`${field} mt-1 block w-24`} type="number" min={5} max={300} value={page.duration_seconds}
            onChange={(e) => updatePage((p) => ({ ...p, duration_seconds: Number(e.target.value) || 5 }))} />
        </label>
        <button className={btn} disabled={pages.length <= 1}
          onClick={() => { onChange({ ...config, pages: pages.filter((_, i) => i !== index) }); onSelect(0) }}>Delete wall page</button>
        <button className={`${btn} ml-auto`} disabled={pages.length >= MAX_PAGES}
          onClick={() => { onChange({ ...config, pages: [...pages, { name: 'Wall page', duration_seconds: 30, widgets: [] }] }); onSelect(pages.length) }}>Add wall page</button>
      </div>
      <ol className="space-y-1" aria-label="Wall cards on this page">
        {page.widgets.map((w, i) => (
          <li key={w.key} draggable onDragStart={() => setDragFrom(i)} onDragOver={(e) => e.preventDefault()}
            onDrop={() => { const from = dragFrom; if (from !== null) updateWidgets((ws) => moveWidget(ws, from, i)); setDragFrom(null) }}
            className="flex items-center gap-2 rounded bg-slate-800 px-3 py-2">
            <span className="cursor-grab text-slate-500" aria-hidden="true">⠿</span>
            <span className="flex-1 text-sm text-white">{wallDashboardWidgetLabel(w.key)}</span>
            <button className={btn} aria-label={`Move up: ${wallDashboardWidgetLabel(w.key)}`} disabled={i === 0} onClick={() => move(w.key, -1)}>↑</button>
            <button className={btn} aria-label={`Move down: ${wallDashboardWidgetLabel(w.key)}`} disabled={i === page.widgets.length - 1} onClick={() => move(w.key, 1)}>↓</button>
            <button className={btn} aria-label={`${w.size === 'wide' ? 'Make normal' : 'Make wide'}: ${wallDashboardWidgetLabel(w.key)}`}
              onClick={() => updateWidgets((ws) => ws.map((x) => (x.key === w.key ? { ...x, size: x.size === 'wide' ? 'normal' : 'wide' } : x)))}>{w.size === 'wide' ? 'Wide' : 'Normal'}</button>
            <button className={btn} aria-label={`Remove: ${wallDashboardWidgetLabel(w.key)}`} onClick={() => updateWidgets((ws) => ws.filter((x) => x.key !== w.key))}>✕</button>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap items-center gap-2">
        {missing.length > 0 && (
          <>
            <select className={field} value={adding} onChange={(e) => setAdding(e.target.value as WallDashboardWidgetKey)} aria-label="Wall card to add">
              <option value="">Add a wall card…</option>
              {missing.map((k) => <option key={k} value={k}>{wallDashboardWidgetLabel(k)}</option>)}
            </select>
            <button className={btn} disabled={!adding} onClick={() => {
              const key = adding
              if (key) updateWidgets((ws) => (ws.some((x) => x.key === key) ? ws : [...ws, { key, size: 'normal' }]))
              setAdding('')
            }}>Add wall card</button>
          </>
        )}
        <button className={`${btn} ml-auto`} onClick={() => { onChange(DEFAULT_WALL_DASHBOARD); onSelect(0) }}>Reset wall dashboard</button>
        {saving && <span className="text-xs text-slate-400">Saving…</span>}
      </div>
    </section>
  )
}
