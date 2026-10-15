import { Link } from 'react-router-dom'
import { useCalendarEvents, useCalendarSources } from '../../api/calendar'
import { usePreferences } from '../../api/prefs'
import { useChoreAction, useChoreInstances } from '../../api/chores'
import { useHAAction, useHAStates, type HAActionExtra, type HAActionName, type HAEntity } from '../../api/homeAssistant'
import HAEntityList from '../../components/HAEntityList'
import { errorDetail } from '../../api/client'
import {
  useDeleteAnnouncement, usePostAnnouncement, useUpdateAnnouncement, useWeather, type DashboardSummary,
} from '../../api/home'
import { useFamilyProgress } from '../../api/rewards'
import Avatar from '../../components/Avatar'
import FamilyProgress from '../../components/FamilyProgress'
import { addDays, format, parseISO, startOfDay } from 'date-fns'
import { useMemo, useState } from 'react'
import { eventDayKeys, eventStart } from '../../lib/dates'
import { formatCents } from '../../lib/money'
import { useAuthStore } from '../../stores/auth'

const card = 'rounded-xl bg-slate-800 p-4'
const heading = 'text-lg font-semibold text-white'

function Card({ title, link, children }: { title: string; link?: { to: string; label: string }; children: React.ReactNode }) {
  return (
    <section className={card} aria-label={title}>
      <div className="mb-3 flex items-center justify-between">
        <h2 className={heading}>{title}</h2>
        {link && <Link to={link.to} className="text-sm text-primary hover:underline">{link.label}</Link>}
      </div>
      {children}
    </section>
  )
}

function Pending() {
  return <div className="h-3 w-40 animate-pulse rounded bg-slate-700" />
}

export function TodaysEvents({ summary }: { summary?: DashboardSummary }) {
  if (!summary) return <Card title="Today's Events"><Pending /></Card>
  // The day window is by overlap in UTC; all-day events are dates, so keep
  // only those that fall on today's date.
  const todays = summary.events_today.filter((ev) => !ev.all_day || eventDayKeys(ev).includes(summary.today))
  return (
    <Card title="Today's Events" link={{ to: '/calendar', label: 'Calendar' }}>
      {todays.length === 0 && <p className="text-sm text-slate-400">No events scheduled for today.</p>}
      <div className="flex flex-col gap-2">
        {todays.map((ev) => (
          <div key={ev.id} className="flex items-center gap-3 rounded bg-slate-700/50 px-3 py-2">
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: ev.source_color_hex }} />
            <span className="flex-1 truncate text-sm text-slate-200">{ev.title}</span>
            <span className="text-xs text-slate-400">
              {ev.all_day ? 'All day' : eventStart(ev).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}

const WEEK_DAYS = 7
const PER_DAY = 4

/** Today and the next six days, grouped by day; follows "Everyone's events / Just mine". */
export function WeekEvents() {
  const { data: prefs } = usePreferences()
  const todayKey = format(new Date(), 'yyyy-MM-dd')
  const [start, end] = useMemo(() => {
    const s = startOfDay(parseISO(todayKey))
    return [s, addDays(s, WEEK_DAYS)]
  }, [todayKey])
  const { data: events } = useCalendarEvents(start, end, prefs?.calendar_scope ?? 'family')
  const title = 'This Week'
  if (!events) return <Card title={title}><Pending /></Card>
  const days = Array.from({ length: WEEK_DAYS }, (_, i) => addDays(start, i))
  const byDay = new Map(days.map((d) => [format(d, 'yyyy-MM-dd'), [] as typeof events]))
  for (const ev of [...events].sort((a, b) => Number(!a.all_day) - Number(!b.all_day) || eventStart(a).getTime() - eventStart(b).getTime())) {
    for (const key of eventDayKeys(ev)) byDay.get(key)?.push(ev)
  }
  const dayName = (d: Date, i: number) => (i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : format(d, 'EEE d MMM'))
  return (
    <Card title={title} link={{ to: '/calendar', label: 'Calendar' }}>
      {events.length === 0 ? <p className="text-sm text-slate-400">Nothing on the calendar this week.</p> : (
        <ol className="space-y-3">
          {days.map((d, i) => {
            const key = format(d, 'yyyy-MM-dd')
            const list = byDay.get(key) ?? []
            return (
              <li key={key} aria-label={dayName(d, i)}>
                <h3 className={`text-xs font-semibold uppercase tracking-wider ${i === 0 ? 'text-primary' : 'text-slate-400'}`}>{dayName(d, i)}</h3>
                {list.length === 0 ? <p className="text-sm text-slate-500">Nothing planned</p> : (
                  <ul className="mt-1 space-y-1">
                    {list.slice(0, PER_DAY).map((ev) => (
                      <li key={`${ev.id}-${key}`} className="flex items-center gap-3 rounded bg-slate-700/50 px-3 py-1.5">
                        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: ev.source_color_hex }} />
                        <span className="flex-1 truncate text-sm text-slate-200">{ev.title}</span>
                        <span className="text-xs text-slate-400">
                          {ev.all_day ? 'All day' : eventStart(ev).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </li>
                    ))}
                    {list.length > PER_DAY && <li className="text-xs text-slate-400">and {list.length - PER_DAY} more</li>}
                  </ul>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </Card>
  )
}

export function MyDay({ summary }: { summary?: DashboardSummary }) {
  const user = useAuthStore((s) => s.user)
  if (!summary) return <Card title="My Day"><Pending /></Card>
  const c = summary.chores
  return (
    <Card title="My Day" link={{ to: '/chores', label: 'Chores' }}>
      <dl className="grid grid-cols-2 gap-3 text-center">
        {user?.role !== 'viewer' && (
          <div className="rounded bg-slate-700/50 p-2"><dt className="text-xs text-slate-400">My chores left</dt>
            <dd className="text-2xl font-bold text-white">{c.mine_open}</dd></div>
        )}
        <div className="rounded bg-slate-700/50 p-2"><dt className="text-xs text-slate-400">Family chores done</dt>
          <dd className="text-2xl font-bold text-white">{c.family_done}/{c.family_done + c.family_open}</dd></div>
        {user?.role !== 'viewer' && (
          <>
            <div className="rounded bg-slate-700/50 p-2"><dt className="text-xs text-slate-400">My points</dt>
              <dd className="text-2xl font-bold text-amber-300">⭐ {summary.points_balance}</dd></div>
            <div className="rounded bg-slate-700/50 p-2"><dt className="text-xs text-slate-400">My allowance</dt>
              <dd className="text-2xl font-bold text-emerald-300">{formatCents(summary.allowance_cents)}</dd></div>
          </>
        )}
      </dl>
    </Card>
  )
}

const AVAILABLE_SHOWN = 6

/** Today's family chores anyone can claim, with a Claim button (not for viewers). */
export function AvailableChores() {
  const user = useAuthStore((s) => s.user)
  const { data: chores } = useChoreInstances('available')
  const act = useChoreAction()
  const [error, setError] = useState<string | null>(null)
  const title = 'Chores Up for Grabs'
  if (!chores) return <Card title={title}><Pending /></Card>
  const canClaim = user?.role === 'admin' || user?.role === 'member'
  const claim = async (id: string, choreTitle: string) => {
    setError(null)
    try {
      await act.mutateAsync({ id, action: 'claim', title: choreTitle })
    } catch (err) {
      setError(errorDetail(err, "Couldn't claim that chore"))
    }
  }
  return (
    <Card title={title} link={{ to: '/chores', label: 'Chores' }}>
      {error && <p role="alert" className="mb-2 text-sm text-red-300">{error}</p>}
      {chores.length === 0 ? <p className="text-sm text-slate-400">No open chores right now.</p> : (
        <ul className="space-y-2">
          {chores.slice(0, AVAILABLE_SHOWN).map((c) => (
            <li key={c.id} className="flex items-center gap-3 rounded bg-slate-700/50 px-3 py-2">
              <span className="flex-1 truncate text-sm text-slate-200">{c.title}</span>
              <span className="text-xs text-amber-300">⭐ {c.points}</span>
              {canClaim && (
                <button className="rounded bg-primary px-2 py-1 text-xs text-white disabled:opacity-50" disabled={act.isPending}
                  aria-label={`Claim: ${c.title}`} onClick={() => claim(c.id, c.title)}>Claim</button>
              )}
            </li>
          ))}
        </ul>
      )}
      {chores.length > AVAILABLE_SHOWN && (
        <p className="mt-2 text-xs text-slate-400">and {chores.length - AVAILABLE_SHOWN} more on the Chores page</p>
      )}
    </Card>
  )
}

/** Home Assistant entities the admin chose (Phase 12). Hidden until Home Assistant is set up. */
export function SmartHome() {
  const user = useAuthStore((s) => s.user)
  const { data } = useHAStates()
  const act = useHAAction()
  const [error, setError] = useState<string | null>(null)
  const title = 'Smart Home'
  if (!data) return <Card title={title}><Pending /></Card>
  if (!data.configured) return null
  const canControl = user?.role === 'admin' || user?.role === 'member'
  const onAction = async (e: HAEntity, action: HAActionName, extra: HAActionExtra = {}) => {
    setError(null)
    try {
      await act.mutateAsync({ entity_id: e.entity_id, action, ...extra })
    } catch (err) {
      setError(errorDetail(err, "That didn't work"))
    }
  }
  return (
    <Card title={title}>
      {error && <p role="alert" className="mb-2 text-sm text-red-300">{error}</p>}
      {!data.available ? <p className="text-sm text-slate-400">{data.error ?? "Home Assistant isn't reachable right now."}</p>
        : data.entities.length === 0 ? (
          <p className="text-sm text-slate-400">
            {user?.role === 'admin' ? <>Choose what shows here under <Link to="/admin/settings" className="text-primary hover:underline">Settings</Link>.</> : 'Nothing chosen yet.'}
          </p>
        ) : <HAEntityList entities={data.entities} onAction={canControl ? onAction : undefined} busy={act.isPending} />}
    </Card>
  )
}

const SLOT: Record<string, string> = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snack: 'Snack' }

export function MealsToday({ summary }: { summary?: DashboardSummary }) {
  if (!summary) return <Card title="Today's Meals"><Pending /></Card>
  return (
    <Card title="Today's Meals" link={{ to: '/meals', label: 'Meals' }}>
      {summary.meals_today.length === 0 ? <p className="text-sm text-slate-400">Nothing planned today.</p> : (
        <ul className="space-y-1 text-sm">
          {summary.meals_today.map((m) => (
            <li key={m.slot} className="flex justify-between gap-3"><span className="text-slate-400">{SLOT[m.slot] ?? m.slot}</span>
              <span className="truncate text-white">{m.title}</span></li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export function Birthdays({ summary }: { summary?: DashboardSummary }) {
  if (!summary) return <Card title="Birthdays"><Pending /></Card>
  return (
    <Card title="Birthdays">
      {summary.birthdays.length === 0 ? <p className="text-sm text-slate-400">None in the next month.</p> : (
        <ul className="space-y-2">
          {summary.birthdays.map((b) => (
            <li key={b.user_id} className="flex items-center gap-3">
              <Avatar name={b.display_name} color={b.color_hex} emoji={b.avatar_value} className="h-8 w-8 text-base" />
              <span className="flex-1 text-white">{b.display_name} turns {b.turns}</span>
              <span className="text-sm text-slate-400">{b.days_away === 0 ? '🎂 Today!' : b.days_away === 1 ? 'Tomorrow'
                : new Date(`${b.date}T00:00:00`).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export function WeatherCard() {
  const user = useAuthStore((s) => s.user)
  const { data: w } = useWeather()
  if (!w) return <Card title="Weather"><Pending /></Card>
  if (!w.configured) {
    return (
      <Card title="Weather">
        <p className="text-sm text-slate-400">
          {user?.role === 'admin' ? <>Pick your town under <Link to="/admin/settings" className="text-primary hover:underline">Settings</Link> to see the forecast here.</> : 'Not set up yet.'}
        </p>
      </Card>
    )
  }
  const unit = w.units === 'celsius' ? '°C' : '°F'
  return (
    <Card title="Weather">
      {w.error ? <p className="text-sm text-slate-400">{w.error}</p> : (
        <>
          <div className="flex items-center gap-3">
            <span className="text-4xl" aria-hidden="true">{w.emoji}</span>
            <div>
              <p className="text-3xl font-bold text-white">{w.temperature}{unit}</p>
              <p className="text-sm text-slate-400">{w.label} · {w.place}</p>
            </div>
          </div>
          <ul className="mt-3 grid grid-cols-4 gap-2 text-center text-xs text-slate-300">
            {(w.days ?? []).map((d) => (
              <li key={d.date} className="rounded bg-slate-700/50 p-1" title={d.label}>
                <p>{new Date(`${d.date}T00:00:00`).toLocaleDateString([], { weekday: 'short' })}</p>
                <p className="text-lg" aria-label={d.label}>{d.emoji}</p>
                <p>{d.high}° / {d.low}°</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}

export function FamilyStars() {
  const { data: rows, isLoading } = useFamilyProgress()
  return (
    <Card title="Family Stars" link={{ to: '/rewards', label: 'Rewards' }}>
      {isLoading ? <Pending /> : <FamilyProgress rows={rows ?? []} />}
    </Card>
  )
}

export function Announcements({ summary }: { summary?: DashboardSummary }) {
  const user = useAuthStore((s) => s.user)
  const post = usePostAnnouncement()
  const update = useUpdateAnnouncement()
  const remove = useDeleteAnnouncement()
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const run = async (fn: () => Promise<unknown>, fallback: string) => {
    setError(null)
    try { await fn() } catch (err) { setError(errorDetail(err, fallback)) }
  }
  if (!summary) return <Card title="Announcements"><Pending /></Card>
  const canPost = !!user && user.role !== 'viewer'
  const mine = (authorId: string | null) => user?.role === 'admin' || authorId === user?.id
  return (
    <Card title="Announcements">
      {error && <p className="mb-2 rounded bg-red-900/50 px-3 py-1 text-sm text-red-300" role="alert">{error}</p>}
      {summary.announcements.length === 0 && <p className="text-sm text-slate-400">Nothing posted.</p>}
      <ul className="space-y-2">
        {summary.announcements.map((a) => (
          <li key={a.id} className="flex items-start gap-2 rounded bg-slate-700/50 px-3 py-2">
            {a.pinned && <span aria-label="Pinned">📌</span>}
            <p className="flex-1 whitespace-pre-wrap text-sm text-slate-100">{a.body}</p>
            {mine(a.author_id) && (
              <span className="flex shrink-0 gap-1 text-xs">
                <button className="text-slate-400 hover:text-white" onClick={() => run(() => update.mutateAsync({ id: a.id, pinned: !a.pinned }), "Couldn't pin that")}>
                  {a.pinned ? 'Unpin' : 'Pin'}</button>
                <button className="text-slate-400 hover:text-white" aria-label={`Remove: ${a.body}`}
                  onClick={() => run(() => remove.mutateAsync(a.id), "Couldn't remove that")}>✕</button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {canPost && (
        <form className="mt-3 flex gap-2" onSubmit={(e) => {
          e.preventDefault()
          run(async () => { await post.mutateAsync({ body: text.trim() }); setText('') }, "Couldn't post that")
        }}>
          <input className="flex-1 rounded border border-slate-600 bg-slate-900 px-3 py-1.5 text-sm text-white" maxLength={1000}
            placeholder="Tell the family…" aria-label="New announcement" value={text} onChange={(e) => setText(e.target.value)} />
          <button type="submit" className="rounded bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50" disabled={!text.trim() || post.isPending}>Post</button>
        </form>
      )}
    </Card>
  )
}

export function SyncStatus() {
  const { data: sources = [], isLoading } = useCalendarSources()
  if (isLoading) return <Card title="Sync Status"><Pending /></Card>
  const errors = sources.filter((s) => s.sync_error)
  return (
    <Card title="Sync Status">
      <p className="text-sm text-slate-400">{sources.length} source{sources.length !== 1 ? 's' : ''} configured</p>
      {errors.length > 0 && (
        <div className="mt-2 rounded bg-red-900/30 px-3 py-2 text-sm text-red-300">
          {errors.length} source{errors.length !== 1 ? 's' : ''} with errors
        </div>
      )}
      {errors.length === 0 && sources.length > 0 && <p className="mt-2 text-sm text-green-400">All sources healthy</p>}
    </Card>
  )
}
