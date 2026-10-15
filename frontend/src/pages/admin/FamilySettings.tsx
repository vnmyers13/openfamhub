import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { MAX_CLOCKS, useFamilySettings, useUpdateFamilySettings, type FamilySettings as Settings } from '../../api/family'
import { allZones, zoneLabel } from '../../lib/timezones'
import HomeAssistantSettings from './HomeAssistantSettings'
import WeatherSettings from './WeatherSettings'

/** Admin › Settings: family name, timezone, the wall sleep schedule, extra wall clocks, the weather location and Home Assistant. */
export default function FamilySettings() {
  const { data } = useFamilySettings()
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-xl">
        <h1 className="mb-6 text-2xl font-bold text-white">Family settings</h1>
        {data ? <SettingsForm initial={data} /> : <p className="text-gray-400">Loading…</p>}
        <div className="mt-6"><WeatherSettings /></div>
        <div className="mt-6"><HomeAssistantSettings /></div>
      </div>
    </div>
  )
}

function SettingsForm({ initial }: { initial: Settings }) {
  const save = useUpdateFamilySettings()
  const [values, setValues] = useState<Settings>(initial)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [zones] = useState(() => allZones(initial.timezone))
  const setSleep = (patch: Partial<Settings['sleep']>) => setValues((v) => ({ ...v, sleep: { ...v.sleep, ...patch } }))
  const clocks = values.clocks ?? []
  const setClock = (i: number, patch: Partial<{ label: string; timezone: string }>) =>
    setValues((v) => ({ ...v, clocks: (v.clocks ?? []).map((c, j) => (j === i ? { ...c, ...patch } : c)) }))
  const addClock = () => setValues((v) => ({ ...v, clocks: [...(v.clocks ?? []), { label: '', timezone: 'Europe/London' }] }))
  const removeClock = (i: number) => setValues((v) => ({ ...v, clocks: (v.clocks ?? []).filter((_, j) => j !== i) }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setMessage(null)
    try {
      await save.mutateAsync(values)
      setMessage({ ok: true, text: 'Saved' })
    } catch (err) {
      setMessage({ ok: false, text: errorDetail(err, 'Could not save the settings') })
    }
  }

  const input = 'w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white disabled:opacity-50'
  return (
    <form onSubmit={submit} className="space-y-5 rounded-xl border border-gray-800 bg-gray-900 p-6">
      {message && (
        <div className={`rounded px-3 py-2 text-sm ${message.ok ? 'bg-green-900/40 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
          {message.text}
        </div>
      )}
      <div>
        <label htmlFor="family-name" className="mb-1 block text-sm text-gray-300">Family name</label>
        <input id="family-name" className={input} value={values.name} maxLength={128} required
          onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))} />
      </div>
      <div>
        <label htmlFor="family-timezone" className="mb-1 block text-sm text-gray-300">Timezone</label>
        <select id="family-timezone" className={input} value={values.timezone}
          onChange={(e) => setValues((v) => ({ ...v, timezone: e.target.value }))}>
          {zones.map((z) => <option key={z} value={z}>{zoneLabel(z)}</option>)}
        </select>
        <p className="mt-1 text-xs text-gray-500">
          Used for calendar times that come without a timezone, and for the wall's sleep schedule.
        </p>
      </div>
      <fieldset className="space-y-3">
        <legend className="mb-1 text-sm font-medium text-gray-300">Wall sleep schedule</legend>
        <label className="flex items-center gap-2 text-sm text-gray-300">
          <input type="checkbox" checked={values.sleep.enabled} onChange={(e) => setSleep({ enabled: e.target.checked })} />
          Turn wall screens off on a schedule
        </label>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="sleep-off" className="mb-1 block text-xs text-gray-400">Screen off at</label>
            <input id="sleep-off" type="time" className={input} value={values.sleep.off}
              disabled={!values.sleep.enabled} onChange={(e) => setSleep({ off: e.target.value })} />
          </div>
          <div>
            <label htmlFor="sleep-on" className="mb-1 block text-xs text-gray-400">Screen on at</label>
            <input id="sleep-on" type="time" className={input} value={values.sleep.on}
              disabled={!values.sleep.enabled} onChange={(e) => setSleep({ on: e.target.value })} />
          </div>
        </div>
        <p className="text-xs text-gray-500">A touch lights the screen for a few minutes while it's asleep.</p>
      </fieldset>
      <fieldset className="space-y-3">
        <legend className="mb-1 text-sm font-medium text-gray-300">Other clocks on the wall</legend>
        <p className="text-xs text-gray-500">Show the time somewhere else under the wall clock, like where Grandma lives. Up to {MAX_CLOCKS}.</p>
        {clocks.map((c, i) => (
          <div key={i} className="flex gap-2">
            <input className={input} value={c.label} maxLength={40} required placeholder="Grandma" aria-label={`Clock ${i + 1} name`}
              onChange={(e) => setClock(i, { label: e.target.value })} />
            <select className={input} value={c.timezone} aria-label={`Clock ${i + 1} timezone`}
              onChange={(e) => setClock(i, { timezone: e.target.value })}>
              {(zones.includes(c.timezone) ? zones : [c.timezone, ...zones]).map((z) => <option key={z} value={z}>{zoneLabel(z)}</option>)}
            </select>
            <button type="button" className="px-2 text-gray-400 hover:text-red-300" aria-label={`Remove clock ${i + 1}`}
              onClick={() => removeClock(i)}>✕</button>
          </div>
        ))}
        <button type="button" onClick={addClock} disabled={clocks.length >= MAX_CLOCKS}
          className="rounded border border-gray-700 px-3 py-1.5 text-sm text-gray-300 hover:border-gray-500 disabled:opacity-50">
          Add a clock
        </button>
      </fieldset>
      <div className="flex justify-end">
        <button type="submit" disabled={save.isPending}
          className="rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">
          {save.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  )
}
