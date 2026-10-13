import { WEEKDAYS, type Repeat } from '../../lib/repeat'
import { input } from './shared'

/** Choose how something repeats: once, every N days, weeks (on days) or months (on a day). */
export default function RepeatPicker({ id, value, onChange }: { id: string; value: Repeat; onChange: (r: Repeat) => void }) {
  const every = value.every
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <label className="sr-only" htmlFor={`${id}-every`}>Repeats</label>
        <select id={`${id}-every`} className={input} value={every}
          onChange={(e) => onChange({ every: e.target.value as Repeat['every'], interval: 1 })}>
          <option value="none">Once</option>
          <option value="day">Daily</option>
          <option value="week">Weekly</option>
          <option value="month">Monthly</option>
        </select>
        {every !== 'none' && (
          <>
            <label className="sr-only" htmlFor={`${id}-interval`}>Every how many</label>
            <input id={`${id}-interval`} type="number" min={1} max={52} className={`${input} w-20`} value={value.interval ?? 1}
              onChange={(e) => onChange({ ...value, interval: Math.max(1, Number(e.target.value) || 1) })} />
          </>
        )}
      </div>
      {every === 'week' && (
        <div className="flex flex-wrap gap-1" role="group" aria-label="On these days">
          {WEEKDAYS.map((d) => {
            const on = value.weekdays?.includes(d.code) ?? false
            return (
              <button key={d.code} type="button" aria-pressed={on}
                className={`rounded px-2 py-1 text-xs ${on ? 'bg-primary text-white' : 'bg-gray-800 text-gray-300'}`}
                onClick={() => {
                  const days = new Set(value.weekdays ?? [])
                  if (on) days.delete(d.code)
                  else days.add(d.code)
                  onChange({ ...value, weekdays: WEEKDAYS.map((w) => w.code).filter((c) => days.has(c)) })
                }}>
                {d.short}
              </button>
            )
          })}
        </div>
      )}
      {every === 'month' && (
        <>
          <label className="sr-only" htmlFor={`${id}-day`}>Day of the month</label>
          <select id={`${id}-day`} className={input} value={value.month_day ?? ''}
            onChange={(e) => onChange({ ...value, month_day: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Same day as the start date</option>
            {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>Day {d}</option>)}
            <option value={-1}>Last day</option>
          </select>
        </>
      )}
    </div>
  )
}
