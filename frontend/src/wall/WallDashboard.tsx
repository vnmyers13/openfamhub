import type { ReactNode } from 'react'
import {
  useWallAnnouncements,
  useWallChores,
  useWallEvents,
  useWallMeals,
  useWallWeather,
  wallDashboardWidgetLabel,
  type WallDashboardPage,
  type WallDashboardWidgetKey,
} from '../api/wall'
import { eventDayKeys, eventStart } from '../lib/dates'
import type { WorldClock } from '../api/family'
import { useWallHAStates } from '../api/homeAssistant'
import HAEntityList from '../components/HAEntityList'
import WallBirthdays from './WallBirthdays'
import WallClock from './WallClock'
import WallProgress from './WallProgress'
import WallRoutines from './WallRoutines'
import WallNotes from './WallNotes'
import { familyDayRange } from './wallDashboardDates'

const card = 'rounded-2xl bg-slate-800/80 p-5 shadow-lg ring-1 ring-white/5'
const title = 'mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400'

function TodayEvents({ timeZone }: { timeZone: string }) {
  const { start, end, dateKey: todayKey } = familyDayRange(new Date(), timeZone)
  const { data: events = [] } = useWallEvents(start, end)
  const todays = events.filter((ev) => !ev.all_day || eventDayKeys(ev).includes(todayKey)).slice(0, 6)
  return <WallCard title="Today's events">{todays.length === 0 ? <Empty text="No events today." /> : <ul className="space-y-2">{todays.map((ev) => (
    <li key={ev.id} className="flex items-center gap-3 rounded bg-slate-700/60 px-3 py-2">
      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: ev.source_color_hex }} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-lg text-white">{ev.title}</span>
        {ev.location && <span className="block truncate text-sm text-slate-400"><span aria-hidden="true">📍 </span><span>{ev.location}</span></span>}
      </span>
      <span className="text-sm text-slate-400">{ev.all_day ? 'All day' : eventStart(ev).toLocaleTimeString([], { timeZone, hour: '2-digit', minute: '2-digit', hour12: false })}</span>
    </li>
  ))}</ul>}</WallCard>
}

function ChoresCard() {
  const { data: chores = [] } = useWallChores()
  const open = chores.filter((c) => c.status !== 'completed' && c.status !== 'missed').slice(0, 6)
  return <WallCard title="Chores">{open.length === 0 ? <Empty text="No chores left today." /> : <ul className="space-y-2">{open.map((c) => (
    <li key={c.id} className="flex items-center justify-between rounded bg-slate-700/60 px-3 py-2 text-lg text-white">
      <span className="truncate">{c.title}</span><span className="text-sm text-amber-300">{c.points} pts</span>
    </li>
  ))}</ul>}</WallCard>
}

function MealsCard({ timeZone }: { timeZone: string }) {
  const { data } = useWallMeals()
  const { dateKey } = familyDayRange(new Date(), timeZone)
  const meals = data?.entries.filter((meal) => meal.day === dateKey) ?? []
  return <WallCard title="Today's meals">{meals.length === 0 ? <Empty text="Nothing planned today." /> : <ul className="space-y-2">{meals.map((m) => (
    <li key={m.slot} className="flex justify-between gap-4 rounded bg-slate-700/60 px-3 py-2 text-lg"><span className="text-slate-400 capitalize">{m.slot}</span><span className="truncate text-white">{m.title}</span></li>
  ))}</ul>}</WallCard>
}

function HomeCard() {
  const { data } = useWallHAStates()
  if (!data) return <WallCard title="Smart home"><Empty text="Loading…" /></WallCard>
  if (!data.configured) return <WallCard title="Smart home"><Empty text="Home Assistant is not set up." /></WallCard>
  if (!data.available) return <WallCard title="Smart home"><Empty text={data.error ?? "Home Assistant isn't reachable right now."} /></WallCard>
  return <WallCard title="Smart home">{data.entities.length === 0 ? <Empty text="Nothing chosen yet." /> : <HAEntityList entities={data.entities} large wall />}</WallCard>
}

function WeatherCard() {
  const { data: w } = useWallWeather()
  if (!w) return <WallCard title="Weather"><Empty text="Loading weather…" /></WallCard>
  if (!w.configured) return <WallCard title="Weather"><Empty text="Weather is not set up." /></WallCard>
  const unit = w.units === 'celsius' ? '°C' : '°F'
  return <WallCard title="Weather">{w.error ? <Empty text={w.error} /> : <div className="space-y-4">
    <div className="flex items-center gap-4"><span className="text-6xl" aria-hidden="true">{w.emoji}</span><div><p className="text-5xl font-bold text-white">{w.temperature}{unit}</p><p className="text-lg text-slate-300">{w.label} · {w.place}</p></div></div>
    <ul className="grid grid-cols-4 gap-2 text-center text-sm text-slate-300">{(w.days ?? []).slice(0, 4).map((d) => <li key={d.date} className="rounded bg-slate-700/60 p-2"><p>{new Date(`${d.date}T00:00:00`).toLocaleDateString([], { weekday: 'short' })}</p><p className="text-2xl">{d.emoji}</p><p>{d.high}° / {d.low}°</p></li>)}</ul>
  </div>}</WallCard>
}

function AnnouncementsCard() {
  const { data: announcements = [] } = useWallAnnouncements()
  return <WallCard title="Announcements">{announcements.length === 0 ? <Empty text="Nothing posted." /> : <ul className="space-y-2">{announcements.map((a) => (
    <li key={a.id} className="rounded bg-slate-700/60 px-3 py-2 text-lg text-white">{a.pinned && <span aria-label="Pinned">📌 </span>}{a.body}</li>
  ))}</ul>}</WallCard>
}

function ProgressCard() {
  return <WallCard title="Family progress"><div className="grid gap-6 lg:grid-cols-2"><WallProgress /><WallBirthdays /></div></WallCard>
}

function BirthdaysCard() {
  return <WallCard title="Birthdays"><WallBirthdays /></WallCard>
}

function NotesCard() {
  return <WallCard title="Notes"><WallNotes /></WallCard>
}

function WallCard({ title: heading, children }: { title: string; children: ReactNode }) {
  return <section className={card} aria-label={heading}><h2 className={title}>{heading}</h2>{children}</section>
}

function Empty({ text }: { text: string }) {
  return <p className="text-lg text-slate-400">{text}</p>
}

function Widget({ widget, timeZone, clocks }: { widget: WallDashboardWidgetKey; timeZone: string; clocks: WorldClock[] }) {
  if (widget === 'clock') return <WallCard title={wallDashboardWidgetLabel(widget)}><WallClock timeZone={timeZone} clocks={clocks} /></WallCard>
  if (widget === 'events') return <TodayEvents timeZone={timeZone} />
  if (widget === 'chores') return <ChoresCard />
  if (widget === 'routines') return <WallCard title={wallDashboardWidgetLabel(widget)}><WallRoutines timeZone={timeZone} /></WallCard>
  if (widget === 'meals') return <MealsCard timeZone={timeZone} />
  if (widget === 'weather') return <WeatherCard />
  if (widget === 'announcements') return <AnnouncementsCard />
  if (widget === 'progress') return <ProgressCard />
  if (widget === 'home') return <HomeCard />
  if (widget === 'notes') return <NotesCard />
  return <BirthdaysCard />
}

export function WallDashboardPageView({ page, timeZone, clocks = [] }: { page: WallDashboardPage; timeZone: string; clocks?: WorldClock[] }) {
  if (page.widgets.length === 0) return <div className="p-8 text-2xl text-slate-400">This wall dashboard page is empty.</div>
  return (
    <div className="grid h-full content-start gap-6 overflow-y-auto p-8 md:grid-cols-2 xl:grid-cols-3">
      {page.widgets.map((w) => <div key={w.key} className={w.size === 'wide' ? 'md:col-span-2' : ''}><Widget widget={w.key} timeZone={timeZone} clocks={clocks} /></div>)}
    </div>
  )
}
