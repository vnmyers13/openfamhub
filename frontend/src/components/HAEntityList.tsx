import { RUNNABLE, SWITCHABLE, stateText, type HAActionName, type HAEntity } from '../api/homeAssistant'

const ICON: Record<string, string> = {
  light: '💡', switch: '🔌', fan: '🌀', input_boolean: '🔘', scene: '🎬', script: '▶️', climate: '🌡️', sensor: '📈', binary_sensor: '🚪',
}

/**
 * Home Assistant entities as rows: a state, and for people who may switch
 * things (`onAction`), a toggle, a Run button or thermostat −/+. Without
 * `onAction` (viewers, the wall) it only shows.
 */
export default function HAEntityList({ entities, onAction, busy = false, large = false }: {
  entities: HAEntity[]; onAction?: (e: HAEntity, action: HAActionName, temperature?: number) => void; busy?: boolean; large?: boolean
}) {
  const btn = `rounded px-2 py-1 ${large ? 'text-base' : 'text-xs'} text-white disabled:opacity-50`
  return (
    <ul className="space-y-2">
      {entities.map((e) => {
        const off = e.state === 'unavailable' || e.state === 'unknown'
        const on = e.state === 'on'
        const step = (by: number) => {
          const target = (e.target_temperature ?? e.current_temperature ?? 20) + by
          onAction?.(e, 'set_temperature', Math.min(e.max_temp ?? 35, Math.max(e.min_temp ?? 5, target)))
        }
        return (
          <li key={e.entity_id} className={`flex items-center gap-3 rounded bg-slate-700/50 px-3 py-2 ${off ? 'opacity-60' : ''}`}>
            <span aria-hidden="true">{ICON[e.domain] ?? '🏠'}</span>
            <span className={`flex-1 truncate ${large ? 'text-lg' : 'text-sm'} text-slate-200`}>{e.name}</span>
            {e.domain === 'climate' && e.target_temperature != null && (
              <span className={`${large ? 'text-base' : 'text-xs'} text-slate-400`}>set {e.target_temperature}{e.unit ?? '°'}</span>
            )}
            <span className={`${large ? 'text-base' : 'text-xs'} ${on ? 'text-amber-300' : 'text-slate-400'}`}>{stateText(e)}</span>
            {onAction && !off && SWITCHABLE.has(e.domain) && (
              <button className={`${btn} ${on ? 'bg-amber-600' : 'bg-slate-600'}`} disabled={busy} aria-pressed={on}
                aria-label={`${on ? 'Turn off' : 'Turn on'}: ${e.name}`} onClick={() => onAction(e, 'toggle')}>{on ? 'On' : 'Off'}</button>
            )}
            {onAction && !off && RUNNABLE.has(e.domain) && (
              <button className={`${btn} bg-primary`} disabled={busy} aria-label={`Run: ${e.name}`} onClick={() => onAction(e, 'turn_on')}>Run</button>
            )}
            {onAction && !off && e.domain === 'climate' && (
              <span className="flex gap-1">
                <button className={`${btn} bg-slate-600`} disabled={busy} aria-label={`Cooler: ${e.name}`} onClick={() => step(-1)}>−</button>
                <button className={`${btn} bg-slate-600`} disabled={busy} aria-label={`Warmer: ${e.name}`} onClick={() => step(1)}>+</button>
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}
