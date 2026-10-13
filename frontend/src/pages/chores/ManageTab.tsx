import { useState } from 'react'
import { errorDetail } from '../../api/client'
import {
  useChoreByUser, useChoreTemplates, useFamilyMembers, useRetireChore, useRetireRoutine, useRoutines,
  useSaveChore, useSaveRoutine, type ChoreTemplate, type Routine, type RoutineStep,
} from '../../api/chores'
import { describeRepeat, type Repeat } from '../../lib/repeat'
import RepeatPicker from './RepeatPicker'
import { Banner, MemberSelect } from './Controls'
import { input, nameOf, primary, subtle } from './shared'

function ChoreForm({ chore, onDone }: { chore?: ChoreTemplate; onDone: () => void }) {
  const { data: members } = useFamilyMembers()
  const save = useSaveChore()
  const [title, setTitle] = useState(chore?.title ?? '')
  const [points, setPoints] = useState(chore?.points ?? 5)
  const [who, setWho] = useState<string | null>(chore?.assigned_to ?? null)
  const [repeat, setRepeat] = useState<Repeat>(chore?.repeat ?? { every: 'day', interval: 1 })
  const [start, setStart] = useState(chore?.start_date ?? '')
  const [error, setError] = useState<string | null>(null)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await save.mutateAsync({
        id: chore?.id, title: title.trim(), points, repeat,
        assignment: who ? 'assigned' : 'claimable', assigned_to: who,
        ...(start ? { start_date: start } : {}),
      })
      onDone()
    } catch (err) {
      setError(errorDetail(err, "Couldn't save the chore"))
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-gray-800 bg-gray-900 p-4" aria-label={chore ? `Edit ${chore.title}` : 'New chore'}>
      <Banner text={error} onClose={() => setError(null)} />
      <div className="grid gap-3 sm:grid-cols-[1fr_6rem_10rem]">
        <div>
          <label htmlFor="chore-title" className="mb-1 block text-xs text-gray-400">Chore</label>
          <input id="chore-title" className={input} value={title} maxLength={128} required onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <label htmlFor="chore-points" className="mb-1 block text-xs text-gray-400">Points</label>
          <input id="chore-points" type="number" min={0} className={input} value={points}
            onChange={(e) => setPoints(Math.max(0, Number(e.target.value) || 0))} />
        </div>
        <div>
          <label htmlFor="chore-who" className="mb-1 block text-xs text-gray-400">Who</label>
          <MemberSelect id="chore-who" value={who} onChange={setWho} members={members} anyoneLabel="Anyone (first to claim)" />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
        <RepeatPicker id="chore-repeat" value={repeat} onChange={setRepeat} />
        <div>
          <label htmlFor="chore-start" className="mb-1 block text-xs text-gray-400">Starting</label>
          <input id="chore-start" type="date" className={input} value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" className={subtle} onClick={onDone}>Cancel</button>
        <button type="submit" className={primary} disabled={save.isPending || !title.trim()}>Save chore</button>
      </div>
    </form>
  )
}

function RoutineForm({ routine, onDone }: { routine?: Routine; onDone: () => void }) {
  const { data: members } = useFamilyMembers()
  const save = useSaveRoutine()
  const [name, setName] = useState(routine?.name ?? '')
  const [who, setWho] = useState<string | null>(routine?.assigned_to ?? null)
  const [start, setStart] = useState(routine?.start_time ?? '07:00')
  const [repeat, setRepeat] = useState<Repeat>(routine?.repeat ?? { every: 'day', interval: 1 })
  const [steps, setSteps] = useState<RoutineStep[]>(routine?.steps ?? [{ title: '', minutes: 5, points: 1 }])
  const [error, setError] = useState<string | null>(null)
  const setStep = (i: number, patch: Partial<RoutineStep>) => setSteps((s) => s.map((x, j) => (j === i ? { ...x, ...patch } : x)))
  const move = (i: number, d: -1 | 1) => setSteps((s) => {
    const next = [...s]
    ;[next[i], next[i + d]] = [next[i + d], next[i]]
    return next
  })
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await save.mutateAsync({ id: routine?.id, name: name.trim(), assigned_to: who, start_time: start || null, repeat,
        steps: steps.filter((s) => s.title.trim()).map((s) => ({ ...s, title: s.title.trim() })) })
      onDone()
    } catch (err) {
      setError(errorDetail(err, "Couldn't save the routine"))
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-gray-800 bg-gray-900 p-4" aria-label={routine ? `Edit ${routine.name}` : 'New routine'}>
      <Banner text={error} onClose={() => setError(null)} />
      <div className="grid gap-3 sm:grid-cols-[1fr_10rem_8rem]">
        <div>
          <label htmlFor="routine-name" className="mb-1 block text-xs text-gray-400">Routine</label>
          <input id="routine-name" className={input} value={name} required maxLength={128} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label htmlFor="routine-who" className="mb-1 block text-xs text-gray-400">Who</label>
          <MemberSelect id="routine-who" value={who} onChange={setWho} members={members} />
        </div>
        <div>
          <label htmlFor="routine-start" className="mb-1 block text-xs text-gray-400">Starts at</label>
          <input id="routine-start" type="time" className={input} value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
      </div>
      <RepeatPicker id="routine-repeat" value={repeat} onChange={setRepeat} />
      <ol className="space-y-2">
        {steps.map((s, i) => (
          <li key={s.id ?? `new-${i}`} className="grid grid-cols-[1fr_5rem_5rem_auto] items-center gap-2">
            <input className={input} aria-label={`Step ${i + 1}`} value={s.title} maxLength={128} placeholder="Step"
              onChange={(e) => setStep(i, { title: e.target.value })} />
            <input className={input} type="number" min={1} max={180} aria-label={`Step ${i + 1} minutes`} value={s.minutes}
              onChange={(e) => setStep(i, { minutes: Math.min(180, Math.max(1, Number(e.target.value) || 1)) })} />
            <input className={input} type="number" min={0} aria-label={`Step ${i + 1} points`} value={s.points}
              onChange={(e) => setStep(i, { points: Math.max(0, Number(e.target.value) || 0) })} />
            <span className="flex gap-1">
              <button type="button" className={subtle} aria-label={`Move step ${i + 1} up`} disabled={i === 0} onClick={() => move(i, -1)}>↑</button>
              <button type="button" className={subtle} aria-label={`Move step ${i + 1} down`} disabled={i === steps.length - 1} onClick={() => move(i, 1)}>↓</button>
              <button type="button" className={subtle} aria-label={`Remove step ${i + 1}`} disabled={steps.length === 1}
                onClick={() => setSteps((x) => x.filter((_, j) => j !== i))}>✕</button>
            </span>
          </li>
        ))}
      </ol>
      <div className="flex justify-between gap-2">
        <button type="button" className={subtle} disabled={steps.length >= 20}
          onClick={() => setSteps((s) => [...s, { title: '', minutes: 5, points: 1 }])}>+ Step</button>
        <span className="flex gap-2">
          <button type="button" className={subtle} onClick={onDone}>Cancel</button>
          <button type="submit" className={primary} disabled={save.isPending || !name.trim()}>Save routine</button>
        </span>
      </div>
    </form>
  )
}

export default function ManageTab() {
  const { data: chores } = useChoreTemplates()
  const { data: routines } = useRoutines()
  const { data: byUser } = useChoreByUser()
  const { data: members } = useFamilyMembers()
  const retireChore = useRetireChore()
  const retireRoutine = useRetireRoutine()
  const [editingChore, setEditingChore] = useState<ChoreTemplate | 'new' | null>(null)
  const [editingRoutine, setEditingRoutine] = useState<Routine | 'new' | null>(null)
  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">Today by person</h2>
        <table className="w-full max-w-lg text-sm">
          <thead><tr className="text-left text-gray-400"><th className="py-1">Who</th><th>To do</th><th>Done</th><th>Missed</th></tr></thead>
          <tbody>
            {(byUser ?? []).map((r) => (
              <tr key={r.user_id ?? 'anyone'} className="border-t border-gray-800 text-gray-200">
                <td className="py-1">{r.display_name}</td><td>{r.pending}</td><td>{r.completed}</td><td>{r.missed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Chores</h2>
          <button className={primary} onClick={() => setEditingChore('new')}>Add chore</button>
        </div>
        {editingChore && <div className="mb-3"><ChoreForm chore={editingChore === 'new' ? undefined : editingChore} onDone={() => setEditingChore(null)} /></div>}
        <ul className="space-y-2">
          {(chores ?? []).map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-2">
              <div>
                <p className="text-white">{c.title}</p>
                <p className="text-xs text-gray-400">{nameOf(members, c.assigned_to)} · {describeRepeat(c.repeat, c.start_date)} · {c.points} pts</p>
              </div>
              <span className="flex gap-2">
                <button className={subtle} aria-label={`Edit ${c.title}`} onClick={() => setEditingChore(c)}>Edit</button>
                <button className={subtle} aria-label={`Stop ${c.title}`}
                  onClick={() => { if (confirm(`Stop "${c.title}"? Past completions stay in the history.`)) retireChore.mutate(c.id) }}>Stop</button>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Routines</h2>
          <button className={primary} onClick={() => setEditingRoutine('new')}>Add routine</button>
        </div>
        {editingRoutine && <div className="mb-3"><RoutineForm routine={editingRoutine === 'new' ? undefined : editingRoutine} onDone={() => setEditingRoutine(null)} /></div>}
        <ul className="space-y-2">
          {(routines ?? []).map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-2">
              <div>
                <p className="text-white">{r.name}</p>
                <p className="text-xs text-gray-400">
                  {nameOf(members, r.assigned_to)} · {r.start_time ?? 'any time'} · {r.steps.map((s) => s.title).join(' → ')}
                </p>
              </div>
              <span className="flex gap-2">
                <button className={subtle} aria-label={`Edit ${r.name}`} onClick={() => setEditingRoutine(r)}>Edit</button>
                <button className={subtle} aria-label={`Stop ${r.name}`}
                  onClick={() => { if (confirm(`Stop the "${r.name}" routine?`)) retireRoutine.mutate(r.id) }}>Stop</button>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
