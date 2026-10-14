import { useState } from 'react'
import { errorDetail } from '../../api/client'
import {
  SLOTS, useClearSlot, usePlan, useRecipes, useSetSlot, useShoppingFromPlan, type PlanEntry, type Slot,
} from '../../api/meals'
import { dayLabel, shiftWeek, weekLabel } from '../../lib/meals'
import { useAuthStore } from '../../stores/auth'
import { Banner } from '../chores/Controls'
import { input, primary, subtle } from '../chores/shared'

const SLOT_LABEL: Record<Slot, string> = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snack: 'Snack' }

function SlotEditor({ day, slot, entry, onDone, onError }: {
  day: string; slot: Slot; entry?: PlanEntry; onDone: () => void; onError: (m: string) => void
}) {
  const { data: recipes } = useRecipes()
  const setSlot = useSetSlot()
  const clear = useClearSlot()
  const [recipeId, setRecipeId] = useState(entry?.recipe_id ?? '')
  const [title, setTitle] = useState(entry && !entry.recipe_id ? entry.title : '')
  const label = `${SLOT_LABEL[slot]} on ${dayLabel(day)}`
  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await setSlot.mutateAsync({ day, slot, recipe_id: recipeId || null, title: recipeId ? null : title.trim() })
      onDone()
    } catch (err) {
      onError(errorDetail(err, "Couldn't save that meal"))
    }
  }
  const remove = async () => {
    try {
      await clear.mutateAsync({ day, slot })
      onDone()
    } catch (err) {
      onError(errorDetail(err, "Couldn't clear that meal"))
    }
  }
  return (
    <form onSubmit={save} className="space-y-2 rounded border border-gray-700 bg-gray-800 p-2" aria-label={`Plan ${label}`}>
      <select className={input} value={recipeId} onChange={(e) => setRecipeId(e.target.value)} aria-label={`Recipe for ${label}`}>
        <option value="">Type something instead…</option>
        {(recipes ?? []).map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}
      </select>
      {!recipeId && (
        <input className={input} placeholder="e.g. Leftovers" maxLength={128} value={title}
          onChange={(e) => setTitle(e.target.value)} aria-label={`What's for ${label}`} />
      )}
      <div className="flex justify-end gap-1">
        {entry && <button type="button" className={subtle} onClick={remove}>Clear</button>}
        <button type="button" className={subtle} onClick={onDone}>Cancel</button>
        <button type="submit" className={primary} disabled={setSlot.isPending || (!recipeId && !title.trim())}>Save</button>
      </div>
    </form>
  )
}

export default function PlanTab({ onShop }: { onShop: () => void }) {
  const user = useAuthStore((s) => s.user)
  const canEdit = !!user && user.role !== 'viewer'
  const [start, setStart] = useState<string | undefined>(undefined)
  const { data: week } = usePlan(start)
  const fromPlan = useShoppingFromPlan()
  const [editing, setEditing] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  if (!week) return null
  const at = (day: string, slot: Slot) => week.entries.find((e) => e.day === day && e.slot === slot)

  const makeList = async () => {
    setError(null)
    try {
      const res = await fromPlan.mutateAsync(week.week_start)
      setNote(res.added || res.removed
        ? `Shopping list updated: ${res.added} added${res.removed ? `, ${res.removed} removed` : ''}.`
        : 'The shopping list already has everything for this week.')
    } catch (err) {
      setError(errorDetail(err, "Couldn't make the shopping list"))
    }
  }

  return (
    <div>
      <Banner text={error} onClose={() => setError(null)} />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button className={subtle} onClick={() => setStart(shiftWeek(week.week_start, -1))} aria-label="Previous week">←</button>
          <h2 className="text-lg font-semibold text-white">{weekLabel(week.week_start)}</h2>
          <button className={subtle} onClick={() => setStart(shiftWeek(week.week_start, 1))} aria-label="Next week">→</button>
          {start && <button className={subtle} onClick={() => setStart(undefined)}>This week</button>}
        </div>
        {canEdit && <button className={primary} disabled={fromPlan.isPending} onClick={makeList}>Make shopping list</button>}
      </div>
      {note && (
        <p className="mb-4 rounded bg-emerald-900/40 px-4 py-2 text-sm text-emerald-200" role="status">
          {note} <button className="underline" onClick={onShop}>Open the list</button>
        </p>
      )}
      <div className="space-y-2">
        {week.days.map((day) => (
          <section key={day} className="rounded-lg border border-gray-800 bg-gray-900 p-3" aria-label={dayLabel(day)}>
            <h3 className="mb-2 text-sm font-semibold text-gray-300">{dayLabel(day)}</h3>
            <div className="grid gap-2 sm:grid-cols-4">
              {SLOTS.map((slot) => {
                const entry = at(day, slot)
                const key = `${day}/${slot}`
                if (editing === key) {
                  return <SlotEditor key={slot} day={day} slot={slot} entry={entry} onDone={() => setEditing(null)} onError={setError} />
                }
                return (
                  <button key={slot} disabled={!canEdit} onClick={() => setEditing(key)}
                    className="min-h-12 rounded border border-gray-800 bg-gray-950 px-2 py-1 text-left disabled:cursor-default"
                    aria-label={`${SLOT_LABEL[slot]} on ${dayLabel(day)}: ${entry ? entry.title : 'nothing planned'}`}>
                    <span className="block text-[11px] uppercase tracking-wider text-gray-500">{SLOT_LABEL[slot]}</span>
                    <span className={`block truncate text-sm ${entry ? 'text-white' : 'text-gray-600'}`}>{entry ? entry.title : canEdit ? '+' : '—'}</span>
                  </button>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
