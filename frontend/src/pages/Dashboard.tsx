import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useDashboardSummary, type DashboardSummary } from '../api/home'
import { DEFAULT_PREFS, usePreferences, useSavePreferences, type DashboardPage, type Preferences } from '../api/prefs'
import { DEFAULT_WALL_DASHBOARD, useFamilyWallDashboardConfig, useSaveFamilyWallDashboardConfig } from '../api/wall'
import { effectivePages, WALLPAPERS, type WidgetKey } from '../lib/dashboard'
import { useAuthStore } from '../stores/auth'
import CustomizeDashboard from './dashboard/CustomizeDashboard'
import WallDashboardEditor from './dashboard/WallDashboardEditor'
import {
  Announcements, Birthdays, FamilyStars, MealsToday, MyDay, SyncStatus, TodaysEvents, WeatherCard,
} from './dashboard/widgets'

const RENDER: Record<WidgetKey, (s?: DashboardSummary) => React.ReactNode> = {
  events: (s) => <TodaysEvents summary={s} />,
  weather: () => <WeatherCard />,
  'my-day': (s) => <MyDay summary={s} />,
  meals: (s) => <MealsToday summary={s} />,
  stars: () => <FamilyStars />,
  announcements: (s) => <Announcements summary={s} />,
  birthdays: (s) => <Birthdays summary={s} />,
  sync: () => <SyncStatus />,
}

function Greeting() {
  const user = useAuthStore((s) => s.user)
  const hour = new Date().getHours()
  let period = 'evening'
  if (hour < 12) period = 'morning'
  else if (hour < 17) period = 'afternoon'
  return (
    <h1 className="text-3xl font-bold text-white drop-shadow">
      Good {period}, {user?.display_name ?? 'there'}!
    </h1>
  )
}

function WallDashboardCustomizer() {
  const { data: config = DEFAULT_WALL_DASHBOARD } = useFamilyWallDashboardConfig()
  const save = useSaveFamilyWallDashboardConfig()
  const [current, setCurrent] = useState(0)
  return <WallDashboardEditor config={config} current={current} onSelect={setCurrent} onChange={(next) => save.mutate(next)} saving={save.isPending} />
}

/** Home: the person's own dashboard pages (or one default page), on their wallpaper. */
export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin'
  const { data: prefs = DEFAULT_PREFS } = usePreferences()
  const save = useSavePreferences()
  const { data: summary } = useDashboardSummary(prefs.calendar_scope)
  const [pageIndex, setPageIndex] = useState(0)
  const [customizing, setCustomizing] = useState(false)
  const pages = effectivePages(prefs.pages, isAdmin)
  const current = Math.min(pageIndex, pages.length - 1)
  const page = pages[current]

  const background = prefs.wallpaper === 'photo' && prefs.wallpaper_media_id
    ? { backgroundImage: `url(/api/media/${prefs.wallpaper_media_id}/wall)`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : undefined
  const gradient = prefs.wallpaper !== 'photo' ? WALLPAPERS[prefs.wallpaper].className : ''

  const qc = useQueryClient()
  // Apply each change to the newest saved prefs (the cache is updated at once
  // on save), not to this render's copy, so rapid edits don't undo each other.
  const savePages = (update: (pages: DashboardPage[]) => DashboardPage[]) => {
    const latest = qc.getQueryData<Preferences>(['preferences']) ?? prefs
    save.mutate({ ...latest, pages: update(effectivePages(latest.pages, isAdmin)) })
  }

  return (
    <div className={`min-h-full ${gradient}`} style={background} data-testid="dashboard">
      <div className="flex flex-col gap-6 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Greeting />
          <div className="flex items-center gap-2">
            {pages.length > 1 && (
              <div className="flex gap-1 rounded-lg bg-slate-900/70 p-1" role="tablist" aria-label="Dashboard pages">
                {pages.map((p, i) => (
                  <button key={`${p.name}-${i}`} role="tab" aria-selected={i === current} onClick={() => setPageIndex(i)}
                    className={`rounded px-3 py-1 text-sm ${i === current ? 'bg-primary text-white' : 'text-slate-300 hover:text-white'}`}>{p.name}</button>
                ))}
              </div>
            )}
            <button className="rounded bg-slate-800/80 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700"
              onClick={() => setCustomizing((c) => !c)} aria-expanded={customizing}>{customizing ? 'Done' : 'Customize'}</button>
          </div>
        </div>
        {customizing && (
          <div className="space-y-4">
            <CustomizeDashboard pages={pages} current={current} isAdmin={isAdmin} onSelect={setPageIndex}
              onChange={savePages} saving={save.isPending} />
            <WallDashboardCustomizer />
          </div>
        )}
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {page.widgets.map((w) => (
            <div key={w.key} className={w.size === 'wide' ? 'md:col-span-2' : ''}>{RENDER[w.key](summary)}</div>
          ))}
        </div>
        {page.widgets.length === 0 && <p className="text-sm text-slate-400">This page is empty. Press Customize to add cards.</p>}
      </div>
    </div>
  )
}
