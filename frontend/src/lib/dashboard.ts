import type { DashboardPage, DashboardWidget, Wallpaper } from '../api/prefs'

/** Dashboard cards, in their default order. */
export const WIDGETS = [
  { key: 'events', label: "Today's events" },
  { key: 'weather', label: 'Weather' },
  { key: 'my-day', label: 'My day' },
  { key: 'meals', label: "Today's meals" },
  { key: 'stars', label: 'Family stars' },
  { key: 'announcements', label: 'Announcements' },
  { key: 'birthdays', label: 'Birthdays' },
  { key: 'sync', label: 'Calendar sync', adminOnly: true },
] as const

export type WidgetKey = (typeof WIDGETS)[number]['key']

export const widgetLabel = (key: WidgetKey) => WIDGETS.find((w) => w.key === key)?.label ?? key

const w = (key: WidgetKey, size: DashboardWidget['size'] = 'normal'): DashboardWidget => ({ key, size })

/** Starting points for a new dashboard page. */
export const TEMPLATES: { name: string; description: string; page: DashboardPage }[] = [
  { name: 'Everything', description: 'Every card', page: { name: 'Home', widgets: WIDGETS.map((x) => w(x.key)) } },
  { name: 'Kids', description: 'Stars, my day and birthdays', page: { name: 'Kids', widgets: [w('stars', 'wide'), w('my-day'), w('birthdays'), w('events')] } },
  { name: 'Parents', description: 'Schedule, meals and notes', page: { name: 'Parents', widgets: [w('events', 'wide'), w('meals'), w('weather'), w('announcements'), w('sync')] } },
  { name: 'Kitchen', description: 'Meals, weather and notes', page: { name: 'Kitchen', widgets: [w('meals', 'wide'), w('weather'), w('announcements')] } },
]

/** The pages to show: saved ones, or one default page; cards someone may not see are dropped. */
export function effectivePages(saved: DashboardPage[], isAdmin: boolean): DashboardPage[] {
  const allowed = (key: WidgetKey) => isAdmin || !WIDGETS.find((x) => x.key === key && 'adminOnly' in x)
  const pages = saved.length ? saved : [TEMPLATES[0].page]
  return pages.map((p) => ({ ...p, widgets: p.widgets.filter((x) => allowed(x.key)) }))
}

/** Move the card at `from` to `to` (drag and drop, or the ↑/↓ buttons). */
export function moveWidget(widgets: DashboardWidget[], from: number, to: number): DashboardWidget[] {
  if (from === to || from < 0 || to < 0 || from >= widgets.length || to >= widgets.length) return widgets
  const next = [...widgets]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

/** Cards not on a page yet, for "Add a card". */
export function missingWidgets(page: DashboardPage, isAdmin: boolean): WidgetKey[] {
  const have = new Set(page.widgets.map((x) => x.key))
  return WIDGETS.filter((x) => (isAdmin || !('adminOnly' in x)) && !have.has(x.key)).map((x) => x.key)
}

/** Gradient wallpapers (Tailwind classes); "photo" uses a family photo instead. */
export const WALLPAPERS: Record<Exclude<Wallpaper, 'photo'>, { label: string; className: string }> = {
  none: { label: 'Plain', className: '' },
  dusk: { label: 'Dusk', className: 'bg-gradient-to-br from-indigo-950 via-slate-900 to-purple-950' },
  ocean: { label: 'Ocean', className: 'bg-gradient-to-br from-sky-950 via-slate-900 to-cyan-950' },
  forest: { label: 'Forest', className: 'bg-gradient-to-br from-emerald-950 via-slate-900 to-lime-950' },
  sunrise: { label: 'Sunrise', className: 'bg-gradient-to-br from-orange-950 via-slate-900 to-rose-950' },
}
