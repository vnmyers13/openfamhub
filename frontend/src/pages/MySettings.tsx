import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient, errorDetail } from '../api/client'
import { useMedia } from '../api/media'
import { DEFAULT_PREFS, usePreferences, useSavePreferences, type Preferences } from '../api/prefs'
import { WALLPAPERS } from '../lib/dashboard'
import { useAuthStore } from '../stores/auth'

const box = 'space-y-3 rounded-xl border border-gray-800 bg-gray-900 p-6'
const choice = (on: boolean) => `rounded-lg border px-3 py-2 text-sm ${on ? 'border-primary bg-primary/10 text-white' : 'border-gray-700 text-gray-300 hover:border-gray-500'}`

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

/** Your own choices: birthday, where the menu goes, whose events you see, and the dashboard wallpaper. */
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
