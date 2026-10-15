import { useState } from 'react'
import { NavLink, useParams } from 'react-router-dom'
import { errorDetail } from '../../api/client'
import { MAX_CLOCKS, useFamilySettings, useUpdateFamilySettings, type FamilySettings as Settings } from '../../api/family'
import { allZones, zoneLabel } from '../../lib/timezones'
import HomeAssistantSettings from './HomeAssistantSettings'
import ServerSettingsForm, { type FieldDef } from './ServerSettingsForm'
import WeatherSettings from './WeatherSettings'

const SETTINGS_SECTIONS = [
  { key: 'family', label: 'Family and wall' },
  { key: 'weather', label: 'Weather' },
  { key: 'notifications', label: 'Notifications' },
  { key: 'home-assistant', label: 'Home Assistant' },
  { key: 'system', label: 'Backups and system' },
] as const

const NTFY: FieldDef[] = [
  { name: 'ntfy_url', label: 'ntfy server', kind: 'url', placeholder: 'https://ntfy.sh', help: 'https://ntfy.sh, or your own ntfy server.' },
  { name: 'ntfy_token', label: 'Access token', kind: 'secret', help: 'Only if your ntfy server needs one.' },
]
const EMAIL: FieldDef[] = [
  { name: 'smtp_host', label: 'Email (SMTP) server', kind: 'text', placeholder: 'smtp.example.com' },
  { name: 'smtp_port', label: 'Port', kind: 'number', help: 'Usually 587 with STARTTLS, 465 with SSL.' },
  { name: 'smtp_security', label: 'Security', kind: 'select', options: [
    { value: 'starttls', label: 'STARTTLS' }, { value: 'ssl', label: 'SSL/TLS' }, { value: 'none', label: 'None (not recommended)' }] },
  { name: 'smtp_username', label: 'User name', kind: 'text' },
  { name: 'smtp_password', label: 'Password', kind: 'secret' },
  { name: 'smtp_from', label: 'From', kind: 'text', placeholder: 'OpenFamHub <hub@example.com>' },
]
const HA: FieldDef[] = [
  { name: 'ha_url', label: 'Home Assistant address', kind: 'url', placeholder: 'http://192.168.1.20:8123',
    help: 'As the OpenFamHub server reaches it; an IP address is safest.' },
  { name: 'ha_token', label: 'Long-lived access token', kind: 'secret',
    help: 'In Home Assistant: your profile › Security › Long-lived access tokens.' },
]
const BACKUPS: FieldDef[] = [
  { name: 'backup_time', label: 'Daily backup at', kind: 'time', help: "In the family's timezone." },
  { name: 'backup_retention_days', label: 'Keep backups for (days)', kind: 'number' },
]
const WALL: FieldDef[] = [
  { name: 'wall_idle_timeout_seconds', label: 'Idle screen after (seconds)', kind: 'number',
    help: 'How long a wall display waits without a touch before it shows the photo screen.' },
]

/**
 * Admin › Settings, in sections: the family and its wall (name, timezone,
 * sleep schedule, clocks), weather, notification servers, Home Assistant,
 * and backups and system. Server settings come from services/server_config.py;
 * anything set in .env shows here but can only be changed there.
 */
export default function FamilySettings() {
  const { section = 'family' } = useParams()
  const current = SETTINGS_SECTIONS.find((s) => s.key === section) ?? SETTINGS_SECTIONS[0]
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-6 text-2xl font-bold text-white">Settings</h1>
        <div className="flex flex-col gap-6 md:flex-row">
          <nav aria-label="Settings sections" className="-mx-1 flex shrink-0 gap-1 overflow-x-auto md:mx-0 md:w-48 md:flex-col">
            {SETTINGS_SECTIONS.map((s) => (
              <NavLink key={s.key} to={s.key === 'family' ? '/admin/settings' : `/admin/settings/${s.key}`} end
                aria-current={s.key === current.key ? 'page' : undefined}
                className={`whitespace-nowrap rounded px-3 py-2 text-sm ${s.key === current.key ? 'bg-primary text-white' : 'text-gray-300 hover:bg-gray-800'}`}>
                {s.label}
              </NavLink>
            ))}
          </nav>
          <div className="min-w-0 flex-1 space-y-6">
            <Section which={current.key} />
          </div>
        </div>
      </div>
    </div>
  )
}

function Section({ which }: { which: (typeof SETTINGS_SECTIONS)[number]['key'] }) {
  const { data } = useFamilySettings()
  switch (which) {
    case 'weather':
      return <WeatherSettings />
    case 'notifications':
      return (
        <>
          <ServerSettingsForm title="ntfy" fields={NTFY} test={{ what: 'ntfy', label: 'Send me a test' }}
            intro={<p className="text-sm text-gray-400">People add their own topic in My settings › Notifications. The test goes to yours.</p>} />
          <ServerSettingsForm title="Email" fields={EMAIL} test={{ what: 'email', label: 'Send me a test' }}
            intro={<p className="text-sm text-gray-400">People add their own address in My settings › Notifications. The test goes to yours.</p>} />
        </>
      )
    case 'home-assistant':
      return (
        <>
          <ServerSettingsForm title="Connection" fields={HA} test={{ what: 'home-assistant', label: 'Test connection' }} />
          <HomeAssistantSettings />
        </>
      )
    case 'system':
      return (
        <>
          <ServerSettingsForm title="Backups" fields={BACKUPS}
            intro={<p className="text-sm text-gray-400">A copy of the database is made every day in data/backups. Copying it off the server is up to the server (see the deployment guide).</p>} />
          <ServerSettingsForm title="Wall displays" fields={WALL} />
        </>
      )
    default:
      return data ? <SettingsForm initial={data} /> : <p className="text-gray-400">Loading…</p>
  }
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
