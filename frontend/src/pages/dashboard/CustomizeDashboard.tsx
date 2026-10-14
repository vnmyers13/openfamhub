import { useState } from 'react'
import type { DashboardPage } from '../../api/prefs'
import { missingWidgets, moveWidget, TEMPLATES, widgetLabel, type WidgetKey } from '../../lib/dashboard'

const btn = 'rounded bg-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-600 disabled:opacity-40'
const field = 'rounded border border-slate-600 bg-slate-900 px-2 py-1 text-sm text-white'
const MAX_PAGES = 6

type Widgets = DashboardPage['widgets']

/**
 * Edit this person's dashboard: pages (from templates), and on each page
 * which cards show, their order (drag, or ↑/↓) and width. Every change saves.
 * Changes are updaters applied to the latest saved pages, so quick edits in
 * a row all land even before the screen re-renders.
 */
export default function CustomizeDashboard({ pages, current, isAdmin, onSelect, onChange, saving }: {
  pages: DashboardPage[]; current: number; isAdmin: boolean; saving: boolean
  onSelect: (i: number) => void; onChange: (update: (pages: DashboardPage[]) => DashboardPage[]) => void
}) {
  const page = pages[current]
  const [dragFrom, setDragFrom] = useState<number | null>(null)
  const [adding, setAdding] = useState<WidgetKey | ''>('')
  const [template, setTemplate] = useState(TEMPLATES[0].name)
  const missing = missingWidgets(page, isAdmin)

  const updatePage = (fn: (p: DashboardPage) => DashboardPage) =>
    onChange((all) => all.map((p, i) => (i === current ? fn(p) : p)))
  const updateWidgets = (fn: (ws: Widgets) => Widgets) => updatePage((p) => ({ ...p, widgets: fn(p.widgets) }))
  const indexOf = (ws: Widgets, key: WidgetKey) => ws.findIndex((w) => w.key === key)
  const move = (key: WidgetKey, by: number) => updateWidgets((ws) => moveWidget(ws, indexOf(ws, key), indexOf(ws, key) + by))

  return (
    <section className="space-y-4 rounded-xl border border-slate-700 bg-slate-900/90 p-4" aria-label="Customize dashboard">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-400">Page name
          <input className={`${field} mt-1 block w-40`} value={page.name} maxLength={40}
            onChange={(e) => { const name = e.target.value || ' '; updatePage((p) => ({ ...p, name })) }} />
        </label>
        <button className={btn} disabled={pages.length <= 1}
          onClick={() => { onChange((all) => all.filter((_, i) => i !== current)); onSelect(0) }}>Delete page</button>
        <span className="ml-auto flex items-end gap-2">
          <label className="text-xs text-slate-400">New page from
            <select className={`${field} mt-1 block`} value={template} onChange={(e) => setTemplate(e.target.value)} aria-label="Template">
              {TEMPLATES.map((t) => <option key={t.name} value={t.name}>{t.name}: {t.description}</option>)}
            </select>
          </label>
          <button className={btn} disabled={pages.length >= MAX_PAGES} onClick={() => {
            const t = TEMPLATES.find((x) => x.name === template) ?? TEMPLATES[0]
            const widgets = t.page.widgets.filter((w) => isAdmin || w.key !== 'sync')
            onChange((all) => [...all, { name: t.page.name, widgets }])
            onSelect(pages.length)
          }}>Add page</button>
        </span>
      </div>

      <ol className="space-y-1" aria-label="Cards on this page">
        {page.widgets.map((w, i) => (
          <li key={w.key} draggable onDragStart={() => setDragFrom(i)} onDragOver={(e) => e.preventDefault()}
            onDrop={() => { const from = dragFrom; if (from !== null) updateWidgets((ws) => moveWidget(ws, from, i)); setDragFrom(null) }}
            className="flex items-center gap-2 rounded bg-slate-800 px-3 py-2">
            <span className="cursor-grab text-slate-500" aria-hidden="true">⠿</span>
            <span className="flex-1 text-sm text-white">{widgetLabel(w.key)}</span>
            <button className={btn} aria-label={`Move up: ${widgetLabel(w.key)}`} disabled={i === 0}
              onClick={() => move(w.key, -1)}>↑</button>
            <button className={btn} aria-label={`Move down: ${widgetLabel(w.key)}`} disabled={i === page.widgets.length - 1}
              onClick={() => move(w.key, 1)}>↓</button>
            <button className={btn} aria-label={`${w.size === 'wide' ? 'Make normal' : 'Make wide'}: ${widgetLabel(w.key)}`}
              onClick={() => updateWidgets((ws) => ws.map((x) => (x.key === w.key ? { ...x, size: x.size === 'wide' ? 'normal' : 'wide' } : x)))}>
              {w.size === 'wide' ? 'Wide' : 'Normal'}</button>
            <button className={btn} aria-label={`Remove: ${widgetLabel(w.key)}`}
              onClick={() => updateWidgets((ws) => ws.filter((x) => x.key !== w.key))}>✕</button>
          </li>
        ))}
      </ol>

      <div className="flex flex-wrap items-center gap-2">
        {missing.length > 0 && (
          <>
            <select className={field} value={adding} onChange={(e) => setAdding(e.target.value as WidgetKey)} aria-label="Card to add">
              <option value="">Add a card…</option>
              {missing.map((k) => <option key={k} value={k}>{widgetLabel(k)}</option>)}
            </select>
            <button className={btn} disabled={!adding} onClick={() => {
              const key = adding
              if (key) updateWidgets((ws) => (ws.some((x) => x.key === key) ? ws : [...ws, { key, size: 'normal' }]))
              setAdding('')
            }}>Add</button>
          </>
        )}
        <button className={`${btn} ml-auto`} onClick={() => { onChange(() => []); onSelect(0) }}>Reset to default</button>
        {saving && <span className="text-xs text-slate-400">Saving…</span>}
      </div>
    </section>
  )
}
