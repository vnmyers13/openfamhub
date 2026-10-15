import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { useRoutines } from '../../api/chores'
import {
  DOMAIN_LABEL, RUNNABLE, useHAConfig, useHAEntities, useHAStatus, useSaveHAConfig, type HAConfig, type HAEntity,
} from '../../api/homeAssistant'

const box = 'space-y-4 rounded-xl border border-gray-800 bg-gray-900 p-6'
const input = 'w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white'
const MAX = 24

/**
 * Admin › Settings › Home Assistant (Phase 12): whether the server reaches
 * Home Assistant (HA_URL, HA_TOKEN in .env), which entities the family sees
 * on the Smart home card, and which scene or script a routine starts.
 */
export default function HomeAssistantSettings() {
  const { data: status } = useHAStatus()
  const { data: config } = useHAConfig()
  const { data: entities, error: listError } = useHAEntities(Boolean(status?.reachable))
  return (
    <section className={box} aria-label="Home Assistant">
      <h2 className="text-lg font-semibold text-white">Home Assistant</h2>
      {!status ? <p className="text-sm text-gray-400">Checking…</p>
        : !status.configured ? (
          <p className="text-sm text-gray-400">
            Not set up. Put <code>HA_URL</code> (for example <code>http://homeassistant.local:8123</code>) and <code>HA_TOKEN</code> (a
            long-lived access token from your Home Assistant profile, under Security) in the server's <code>.env</code>, then restart.
          </p>
        ) : !status.reachable ? <p className="text-sm text-red-300" role="alert">{status.error}</p>
          : <p className="text-sm text-green-300">Connected.</p>}
      {listError && <p className="text-sm text-red-300" role="alert">{errorDetail(listError, "Couldn't list Home Assistant's entities")}</p>}
      {status?.reachable && config && entities && <Chooser key={JSON.stringify(config)} config={config} entities={entities} />}
    </section>
  )
}

function Chooser({ config, entities }: { config: HAConfig; entities: HAEntity[] }) {
  const save = useSaveHAConfig()
  const { data: routines = [] } = useRoutines()
  const [chosen, setChosen] = useState<string[]>(config.entities)
  const [scenes, setScenes] = useState<Record<string, string>>(config.routine_scenes)
  const [filter, setFilter] = useState('')
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const needle = filter.trim().toLowerCase()
  const shown = entities.filter((e) => !needle || e.name.toLowerCase().includes(needle) || e.entity_id.includes(needle))
  const groups = [...new Set(shown.map((e) => e.domain))]
  const runnable = entities.filter((e) => RUNNABLE.has(e.domain))
  const timed = routines.filter((r) => r.start_time)
  const toggle = (id: string) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= MAX ? c : [...c, id]))
  const submit = async () => {
    setMessage(null)
    const routine_scenes = Object.fromEntries(Object.entries(scenes).filter(([id, target]) => target && timed.some((r) => r.id === id)))
    try {
      await save.mutateAsync({ entities: chosen, routine_scenes })
      setMessage({ ok: true, text: 'Saved.' })
    } catch (err) {
      setMessage({ ok: false, text: errorDetail(err, "Couldn't save") })
    }
  }
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-gray-300">On the Smart home card ({chosen.length} of up to {MAX})</h3>
        <input className={input} aria-label="Find an entity" placeholder="Find…" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <div className="max-h-80 space-y-3 overflow-y-auto pr-1">
          {groups.map((d) => (
            <fieldset key={d}>
              <legend className="text-xs uppercase tracking-wider text-gray-500">{DOMAIN_LABEL[d] ?? d}</legend>
              {shown.filter((e) => e.domain === d).map((e) => (
                <label key={e.entity_id} className="flex items-center gap-2 py-0.5 text-sm text-gray-200">
                  <input type="checkbox" checked={chosen.includes(e.entity_id)} onChange={() => toggle(e.entity_id)} />
                  <span className="flex-1 truncate">{e.name}</span>
                  <span className="text-xs text-gray-500">{e.entity_id}</span>
                </label>
              ))}
            </fieldset>
          ))}
          {groups.length === 0 && <p className="text-sm text-gray-500">Nothing matches.</p>}
        </div>
        <p className="text-xs text-gray-500">The card shows them in the order you tick them. Members and admins can switch them; viewers and the wall only see them.</p>
      </div>
      {timed.length > 0 && runnable.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-gray-300">Start a scene or script with a routine</h3>
          {timed.map((r) => (
            <label key={r.id} className="flex items-center gap-2 text-sm text-gray-200">
              <span className="flex-1">{r.name} <span className="text-gray-500">at {r.start_time}</span></span>
              <select className="rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-white" aria-label={`Scene for ${r.name}`}
                value={scenes[r.id] ?? ''} onChange={(e) => setScenes((s) => ({ ...s, [r.id]: e.target.value }))}>
                <option value="">Nothing</option>
                {runnable.map((e) => <option key={e.entity_id} value={e.entity_id}>{e.name}</option>)}
              </select>
            </label>
          ))}
          <p className="text-xs text-gray-500">It runs at the routine's start time on the days the routine runs, and is skipped if Home Assistant is down for more than a few minutes.</p>
        </div>
      )}
      <div className="flex items-center gap-3">
        <button className="rounded bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50" disabled={save.isPending} onClick={submit}>Save</button>
        {message && <p className={`text-sm ${message.ok ? 'text-green-300' : 'text-red-300'}`} role={message.ok ? 'status' : 'alert'}>{message.text}</p>}
      </div>
    </div>
  )
}
