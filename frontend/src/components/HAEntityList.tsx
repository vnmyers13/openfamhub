import { useEffect, useRef, useState } from 'react'
import {
  HVAC_LABEL, RUNNABLE, SWITCHABLE, stateText, useHAHistory, type HAActionExtra, type HAActionName, type HAEntity,
} from '../api/homeAssistant'

const ICON: Record<string, string> = {
  light: '💡', switch: '🔌', fan: '🌀', input_boolean: '🔘', scene: '🎬', script: '▶️', climate: '🌡️', sensor: '📈', binary_sensor: '🚪',
}
const DIM_DELAY_MS = 400

export type HAOnAction = (e: HAEntity, action: HAActionName, extra?: HAActionExtra) => void

/**
 * Home Assistant entities as rows: a state, and for people who may switch
 * things (`onAction`), a toggle, a Run button, a dimmer, or thermostat −/+
 * and mode. Numeric sensors get a day's trend line. Without `onAction`
 * (viewers, the wall) it only shows; `wall` reads history through the
 * paired display's endpoint.
 */
export default function HAEntityList({ entities, onAction, busy = false, large = false, wall = false }: {
  entities: HAEntity[]; onAction?: HAOnAction; busy?: boolean; large?: boolean; wall?: boolean
}) {
  return (
    <ul className="space-y-2">
      {entities.map((e) => <Row key={e.entity_id} e={e} onAction={onAction} busy={busy} large={large} wall={wall} />)}
    </ul>
  )
}

function Row({ e, onAction, busy, large, wall }: { e: HAEntity; onAction?: HAOnAction; busy: boolean; large: boolean; wall: boolean }) {
  const small = large ? 'text-base' : 'text-xs'
  const btn = `rounded px-2 py-1 ${small} text-white disabled:opacity-50`
  const off = e.state === 'unavailable' || e.state === 'unknown'
  const on = e.state === 'on'
  const can = Boolean(onAction) && !off
  const step = (by: number) => {
    const target = (e.target_temperature ?? e.current_temperature ?? 20) + by
    onAction?.(e, 'set_temperature', { temperature: Math.min(e.max_temp ?? 35, Math.max(e.min_temp ?? 5, target)) })
  }
  const numeric = e.domain === 'sensor' && !off && Number.isFinite(Number(e.state))
  return (
    <li className={`rounded bg-slate-700/50 px-3 py-2 ${off ? 'opacity-60' : ''}`}>
      <div className="flex items-center gap-3">
        <span aria-hidden="true">{ICON[e.domain] ?? '🏠'}</span>
        <span className={`flex-1 truncate ${large ? 'text-lg' : 'text-sm'} text-slate-200`}>{e.name}</span>
        {e.domain === 'climate' && e.target_temperature != null && (
          <span className={`${small} text-slate-400`}>set {e.target_temperature}{e.unit ?? '°'}</span>
        )}
        <span className={`${small} ${on ? 'text-amber-300' : 'text-slate-400'}`}>{stateText(e)}</span>
        {can && SWITCHABLE.has(e.domain) && (
          <button className={`${btn} ${on ? 'bg-amber-600' : 'bg-slate-600'}`} disabled={busy} aria-pressed={on}
            aria-label={`${on ? 'Turn off' : 'Turn on'}: ${e.name}`} onClick={() => onAction?.(e, 'toggle')}>{on ? 'On' : 'Off'}</button>
        )}
        {can && RUNNABLE.has(e.domain) && (
          <button className={`${btn} bg-primary`} disabled={busy} aria-label={`Run: ${e.name}`} onClick={() => onAction?.(e, 'turn_on')}>Run</button>
        )}
        {can && e.domain === 'climate' && (
          <span className="flex gap-1">
            <button className={`${btn} bg-slate-600`} disabled={busy} aria-label={`Cooler: ${e.name}`} onClick={() => step(-1)}>−</button>
            <button className={`${btn} bg-slate-600`} disabled={busy} aria-label={`Warmer: ${e.name}`} onClick={() => step(1)}>+</button>
          </span>
        )}
      </div>
      {can && e.domain === 'light' && e.dimmable && on && <Dimmer key={e.brightness ?? 'unset'} e={e} onAction={onAction!} disabled={busy} />}
      {can && e.domain === 'climate' && (e.hvac_modes?.length ?? 0) > 1 && (
        <div className="mt-2 flex items-center gap-2">
          <span className={`${small} text-slate-400`}>Mode</span>
          <select className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white disabled:opacity-50" disabled={busy}
            aria-label={`Mode: ${e.name}`} value={e.state} onChange={(ev) => onAction?.(e, 'set_hvac_mode', { hvac_mode: ev.target.value })}>
            {e.hvac_modes!.map((m) => <option key={m} value={m}>{HVAC_LABEL[m] ?? m}</option>)}
          </select>
        </div>
      )}
      {numeric && <Trend entityId={e.entity_id} name={e.name} wall={wall} />}
    </li>
  )
}

/** A brightness slider that sends once the hand stops moving. */
function Dimmer({ e, onAction, disabled }: { e: HAEntity; onAction: HAOnAction; disabled: boolean }) {
  const [value, setValue] = useState(e.brightness ?? 100)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])
  const change = (n: number) => {
    setValue(n)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => onAction(e, 'set_brightness', { brightness: n }), DIM_DELAY_MS)
  }
  return (
    <div className="mt-2 flex items-center gap-2">
      <input type="range" min={1} max={100} value={value} disabled={disabled} className="flex-1 accent-amber-500"
        aria-label={`Brightness: ${e.name}`} onChange={(ev) => change(Number(ev.target.value))} />
      <span className="w-10 text-right text-xs text-slate-400">{value}%</span>
    </div>
  )
}

const W = 200
const H = 36

/** A sensor's last day as a line, with its low and high. */
function Trend({ entityId, name, wall }: { entityId: string; name: string; wall: boolean }) {
  const { data } = useHAHistory(entityId, wall)
  if (!data || data.points.length < 2 || data.low == null || data.high == null) return null
  const span = data.high - data.low || 1
  const times = data.points.map(([t]) => new Date(t).getTime())
  const t0 = times[0]
  const tSpan = times[times.length - 1] - t0 || 1
  const path = data.points.map(([, v], i) => `${((times[i] - t0) / tSpan * W).toFixed(1)},${(H - 2 - (v - data.low!) / span * (H - 4)).toFixed(1)}`).join(' ')
  const unit = data.unit ? ` ${data.unit}` : ''
  return (
    <div className="mt-1 flex items-center gap-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-8 flex-1" preserveAspectRatio="none" role="img"
        aria-label={`${name}, last 24 hours: low ${data.low}${unit}, high ${data.high}${unit}`}>
        <polyline points={path} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" className="text-sky-400" />
      </svg>
      <span className="text-xs text-slate-400">{data.low}–{data.high}{unit}</span>
    </div>
  )
}
