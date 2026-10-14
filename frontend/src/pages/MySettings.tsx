import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient, errorDetail } from '../api/client'
import { useMedia } from '../api/media'
import { DEFAULT_NOTIFICATIONS, DEFAULT_PREFS, usePreferences, useSavePreferences, type NotificationPrefs, type Preferences } from '../api/prefs'
import { pushState, sendTestPush, turnOffPush, turnOnPush, type PushState } from '../lib/push'
import { WALLPAPERS } from '../lib/dashboard'
import { AVATARS } from '../lib/avatars'
import Avatar from '../components/Avatar'
import { useAuthStore } from '../stores/auth'

const box = 'space-y-3 rounded-xl border border-gray-800 bg-gray-900 p-6'
const choice = (on: boolean) => `rounded-lg border px-3 py-2 text-sm ${on ? 'border-primary bg-primary/10 text-white' : 'border-gray-700 text-gray-300 hover:border-gray-500'}`

/** Name, color and avatar: anyone may change their own (Admin › Users changes anyone's). */
function Profile() {
  const user = useAuthStore((s) => s.user)!
  const setUser = useAuthStore((s) => s.setUser)
  const qc = useQueryClient()
  const [name, setName] = useState(user.display_name)
  const startColor = user.color_hex || '#4F46E5'
  const [color, setColor] = useState(startColor)
  const [avatar, setAvatar] = useState<string | null>(user.avatar_value ?? null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const save = useMutation({
    mutationFn: async () => (await apiClient.patch(`/users/${user.id}`, { display_name: name.trim(), color_hex: color, ...(avatar ? { avatar } : {}) })).data,
    onSuccess: () => {
      setUser({ ...user, display_name: name.trim(), color_hex: color, ...(avatar ? { avatar_type: 'emoji', avatar_value: avatar } : {}) })
      setMessage({ ok: true, text: 'Saved' })
      for (const key of ['users', 'auth-profiles', 'progress', 'dashboard']) qc.invalidateQueries({ queryKey: [key] })
    },
    onError: (err) => setMessage({ ok: false, text: errorDetail(err, "Couldn't save your profile") }),
  })
  const changed = name.trim() !== user.display_name || color.toLowerCase() !== startColor.toLowerCase() || avatar !== (user.avatar_value ?? null)
  return (
    <section className={box} aria-label="Profile">
      <h2 className="text-sm font-medium text-gray-300">Me</h2>
      <div className="flex items-center gap-3">
        <Avatar name={name || user.display_name} color={color} emoji={avatar} className="h-12 w-12 text-2xl" />
        <input className="flex-1 rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white" aria-label="My name"
          value={name} maxLength={100} onChange={(e) => setName(e.target.value)} />
        <input type="color" aria-label="My color" className="h-10 w-12 cursor-pointer rounded border border-gray-700 bg-gray-800"
          value={color} onChange={(e) => setColor(e.target.value)} />
      </div>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="My avatar">
        {AVATARS.map((a) => (
          <button key={a} role="radio" aria-checked={avatar === a} aria-label={`Avatar ${a}`} onClick={() => setAvatar(a)}
            className={`flex h-9 w-9 items-center justify-center rounded-full text-lg ${avatar === a ? 'ring-2 ring-white' : ''}`}
            style={{ backgroundColor: color }}>{a}</button>
        ))}
      </div>
      <div className="flex items-center gap-3">
        <button className="rounded bg-primary px-3 py-2 text-sm text-white disabled:opacity-50"
          disabled={save.isPending || !changed || !name.trim()} onClick={() => save.mutate()}>Save</button>
        {message && <span className={`text-sm ${message.ok ? 'text-green-300' : 'text-red-300'}`}>{message.text}</span>}
      </div>
    </section>
  )
}

function Birthday({ userId }: { userId: string }) {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['user', userId], queryFn: async () => (await apiClient.get(`/users/${userId}`)).data as { birthday: string | null } })
  const [value, setValue] = useState<string | null>(null)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const save = useMutation({
    mutationFn: async (birthday: string | null) => apiClient.patch(`/users/${userId}`, { birthday }),
    onSuccess: () => {
      setMessage({ ok: true, text: 'Saved' })
      qc.invalidateQueries({ queryKey: ['user', userId] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (err) => setMessage({ ok: false, text: errorDetail(err, "Couldn't save your birthday") }),
  })
  const current = value ?? data?.birthday ?? ''
  return (
    <section className={box} aria-label="Birthday">
      <h2 className="text-sm font-medium text-gray-300">My birthday</h2>
      <div className="flex gap-2">
        <input type="date" aria-label="My birthday" className="rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white"
          value={current} onChange={(e) => setValue(e.target.value)} />
        <button className="rounded bg-primary px-3 py-2 text-sm text-white disabled:opacity-50" disabled={save.isPending || value === null}
          onClick={() => save.mutate(current || null)}>Save</button>
      </div>
      {message && <p className={`text-sm ${message.ok ? 'text-green-300' : 'text-red-300'}`}>{message.text}</p>}
      <p className="text-xs text-gray-500">It shows on the family calendar and the dashboard. Leave it empty to hide it.</p>
    </section>
  )
}

const STATE_TEXT: Record<PushState, string> = {
  on: 'On for this device.',
  off: 'Off on this device.',
  blocked: 'Notifications are blocked for OpenFamHub on this device. Allow them in the browser or phone settings, then come back.',
  'install-first': 'On an iPhone or iPad, add OpenFamHub to your Home Screen first (Share › Add to Home Screen), open it from there, then turn notifications on here.',
  unsupported: "This browser can't show notifications from OpenFamHub.",
}

/**
 * Reminders on your devices (Phase 11). Turning them on is per device; which
 * reminders you get is saved with your preferences and applies to all of them.
 */
function Notifications({ prefs, isAdmin, onChange }: {
  prefs: NotificationPrefs; isAdmin: boolean; onChange: (n: NotificationPrefs) => void
}) {
  const [state, setState] = useState<PushState | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  useEffect(() => { void pushState().then(setState) }, [])
  const run = async (fn: () => Promise<string | void>) => {
    setBusy(true)
    setMessage(null)
    try {
      const text = await fn()
      if (text) setMessage({ ok: true, text })
      setState(await pushState())
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error && !('response' in err) ? err.message : errorDetail(err, "Couldn't change notifications") })
    } finally {
      setBusy(false)
    }
  }
  const set = (patch: Partial<NotificationPrefs>) => onChange({ ...prefs, ...patch })
  const select = 'rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-white'
  return (
    <section className={box} aria-label="Notifications">
      <h2 className="text-sm font-medium text-gray-300">Notifications</h2>
      {state && <p className="text-sm text-gray-300">{STATE_TEXT[state]}</p>}
      <div className="flex flex-wrap gap-2">
        {state === 'off' && (
          <button className="rounded bg-primary px-3 py-2 text-sm text-white disabled:opacity-50" disabled={busy}
            onClick={() => run(async () => { await turnOnPush() })}>Turn on for this device</button>
        )}
        {state === 'on' && (
          <>
            <button className="rounded border border-gray-700 px-3 py-2 text-sm text-gray-200 disabled:opacity-50" disabled={busy}
              onClick={() => run(async () => ((await sendTestPush()) > 0 ? 'Sent. It should show up in a moment.' : "It didn't go through. Try turning notifications off and on again."))}>
              Send a test</button>
            <button className="rounded border border-gray-700 px-3 py-2 text-sm text-gray-400 disabled:opacity-50" disabled={busy}
              onClick={() => run(async () => { await turnOffPush() })}>Turn off</button>
          </>
        )}
      </div>
      {message && <p className={`text-sm ${message.ok ? 'text-green-300' : 'text-red-300'}`} role={message.ok ? 'status' : 'alert'}>{message.text}</p>}
      <div className="space-y-3 border-t border-gray-800 pt-3 text-sm text-gray-300">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="notify-events">Before events</label>
          <select id="notify-events" className={select} value={prefs.events}
            onChange={(e) => set({ events: e.target.value as NotificationPrefs['events'] })}>
            <option value="off">No reminders</option>
            <option value="mine">Events I added</option>
            <option value="all">All family events</option>
          </select>
          {prefs.events !== 'off' && (
            <select className={select} aria-label="How long before" value={prefs.event_minutes}
              onChange={(e) => set({ event_minutes: Number(e.target.value) as NotificationPrefs['event_minutes'] })}>
              {[5, 10, 15, 30, 60].map((m) => <option key={m} value={m}>{m === 60 ? '1 hour' : `${m} minutes`} before</option>)}
            </select>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={prefs.daily} onChange={(e) => set({ daily: e.target.checked })} />
            A morning list of my chores and to-dos
          </label>
          {prefs.daily && (
            <input type="time" className={select} aria-label="Morning list time" value={prefs.daily_time}
              onChange={(e) => e.target.value && set({ daily_time: e.target.value })} />
          )}
        </div>
        {isAdmin && (
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={prefs.rewards} onChange={(e) => set({ rewards: e.target.checked })} />
            Reward requests waiting for a yes
          </label>
        )}
        <p className="text-xs text-gray-500">These choices apply to every device you've turned on. Nothing is sent during the wall's sleep hours.</p>
      </div>
    </section>
  )
}

/** Your own choices: name, color and avatar, birthday, where the menu goes, whose events you see, and the dashboard wallpaper. */
export default function MySettings() {
  const user = useAuthStore((s) => s.user)
  const { data: prefs = DEFAULT_PREFS } = usePreferences()
  const save = useSavePreferences()
  const { data: media = [] } = useMedia()
  const photos = media.filter((m) => m.kind === 'photo' && m.status === 'ready')
  const set = (patch: Partial<Preferences>) => save.mutate({ ...prefs, ...patch })
  if (!user) return null
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-xl space-y-6">
        <h1 className="text-2xl font-bold text-white">My settings</h1>
        {save.isError && <p className="rounded bg-red-900/50 px-3 py-2 text-sm text-red-300" role="alert">{errorDetail(save.error, "Couldn't save that")}</p>}
        <Profile />
        <Notifications prefs={prefs.notifications ?? DEFAULT_NOTIFICATIONS} isAdmin={user.role === 'admin'}
          onChange={(notifications) => set({ notifications })} />
        {user.role !== 'viewer' && <Birthday userId={user.id} />}
        <section className={box} aria-label="Menu">
          <h2 className="text-sm font-medium text-gray-300">Menu</h2>
          <div className="flex gap-2" role="radiogroup" aria-label="Menu position">
            {(['side', 'top'] as const).map((n) => (
              <button key={n} role="radio" aria-checked={prefs.nav === n} className={choice(prefs.nav === n)} onClick={() => set({ nav: n })}>
                {n === 'side' ? 'Down the side' : 'Across the top'}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500">On a phone the menu stays at the bottom.</p>
        </section>
        <section className={box} aria-label="Calendar">
          <h2 className="text-sm font-medium text-gray-300">Calendar and Home show</h2>
          <div className="flex gap-2" role="radiogroup" aria-label="Whose events">
            {(['family', 'mine'] as const).map((s) => (
              <button key={s} role="radio" aria-checked={prefs.calendar_scope === s} className={choice(prefs.calendar_scope === s)}
                onClick={() => set({ calendar_scope: s })}>{s === 'family' ? "Everyone's events" : 'Just the events I added'}</button>
            ))}
          </div>
        </section>
        <section className={box} aria-label="Wallpaper">
          <h2 className="text-sm font-medium text-gray-300">Home wallpaper</h2>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Wallpaper">
            {(Object.keys(WALLPAPERS) as (keyof typeof WALLPAPERS)[]).map((k) => (
              <button key={k} role="radio" aria-checked={prefs.wallpaper === k}
                className={`${choice(prefs.wallpaper === k)} ${WALLPAPERS[k].className}`} onClick={() => set({ wallpaper: k, wallpaper_media_id: null })}>
                {WALLPAPERS[k].label}
              </button>
            ))}
          </div>
          {photos.length > 0 ? (
            <>
              <p className="text-xs text-gray-500">Or use a family photo:</p>
              <div className="grid grid-cols-4 gap-2">
                {photos.slice(0, 16).map((p) => (
                  <button key={p.id} aria-label={`Use photo ${p.original_name}`} aria-pressed={prefs.wallpaper === 'photo' && prefs.wallpaper_media_id === p.id}
                    className={`overflow-hidden rounded ${prefs.wallpaper === 'photo' && prefs.wallpaper_media_id === p.id ? 'ring-2 ring-primary' : ''}`}
                    onClick={() => set({ wallpaper: 'photo', wallpaper_media_id: p.id })}>
                    <img src={p.thumb_url} alt="" className="aspect-square w-full object-cover" />
                  </button>
                ))}
              </div>
            </>
          ) : <p className="text-xs text-gray-500">Add photos under <Link to="/photos" className="text-primary hover:underline">Photos</Link> to use one as wallpaper.</p>}
        </section>
        <p className="text-sm text-gray-400">To choose and arrange the cards on Home, press <b>Customize</b> there.</p>
      </div>
    </div>
  )
}
