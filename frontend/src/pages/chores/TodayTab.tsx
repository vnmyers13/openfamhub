import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { useChoreAction, useChoreInstances, useChoreStats, useFamilyMembers, type ChoreInstance } from '../../api/chores'
import { useAuthStore } from '../../stores/auth'
import { choreActions, type ChoreAction as Action } from '../../lib/choreActions'
import { Banner } from './Controls'
import { nameOf, primary, subtle } from './shared'

const LABELS: Record<Action, string> = { claim: "I'll do it", unclaim: 'Give back', complete: 'Done', undo: 'Undo' }

function ChoreRow({ chore, onAction, busy }: { chore: ChoreInstance; onAction: (a: Action) => void; busy: boolean }) {
  const user = useAuthStore((s) => s.user)
  const { data: members } = useFamilyMembers()
  const done = chore.status === 'completed'
  const who = chore.assigned_to ? nameOf(members, chore.assigned_to) : chore.claimed_by ? `${nameOf(members, chore.claimed_by)} (claimed)` : 'Anyone'
  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-3">
      <div className="min-w-0">
        <p className={`truncate font-medium ${done ? 'text-gray-500 line-through' : 'text-white'}`}>{chore.title}</p>
        <p className="text-xs text-gray-400">
          {who} · {chore.points} pt{chore.points === 1 ? '' : 's'}{chore.status === 'missed' ? ' · missed' : ''}
        </p>
      </div>
      <div className="flex shrink-0 gap-2">
        {choreActions(chore, user).map((a) => (
          <button key={a} className={a === 'complete' ? primary : subtle} disabled={busy}
            onClick={() => onAction(a)} aria-label={`${LABELS[a]}: ${chore.title}`}>
            {LABELS[a]}
          </button>
        ))}
      </div>
    </li>
  )
}

function Section({ title, chores, empty, onAction, busy }: {
  title: string; chores: ChoreInstance[] | undefined; empty: string; onAction: (c: ChoreInstance, a: Action) => void; busy: boolean
}) {
  return (
    <section className="mb-6">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">{title}</h2>
      {chores && chores.length === 0 ? <p className="text-sm text-gray-500">{empty}</p> : (
        <ul className="space-y-2">
          {(chores ?? []).map((c) => <ChoreRow key={c.id} chore={c} busy={busy} onAction={(a) => onAction(c, a)} />)}
        </ul>
      )}
    </section>
  )
}

export default function TodayTab() {
  const user = useAuthStore((s) => s.user)
  const mine = useChoreInstances('mine')
  const available = useChoreInstances('available')
  const family = useChoreInstances('family')
  const { data: stats } = useChoreStats()
  const act = useChoreAction()
  const [error, setError] = useState<string | null>(null)
  const isAdmin = user?.role === 'admin'
  const onAction = async (c: ChoreInstance, action: Action) => {
    setError(null)
    try {
      await act.mutateAsync({ id: c.id, action })
    } catch (err) {
      setError(errorDetail(err, "That didn't work"))
    }
  }
  return (
    <div>
      {stats && user?.role !== 'viewer' && (
        <div className="mb-6 flex flex-wrap gap-4 rounded-lg border border-gray-800 bg-gray-900 px-4 py-3 text-sm text-gray-300">
          <span>⭐ <strong className="text-white">{stats.points_balance}</strong> points</span>
          <span>🔥 {stats.streak_days}-day streak</span>
          <span>✅ {stats.completed_this_week} done this week</span>
        </div>
      )}
      <Banner text={error} onClose={() => setError(null)} />
      {user?.role !== 'viewer' && (
        <Section title="My chores" chores={mine.data} empty="Nothing for you today." onAction={onAction} busy={act.isPending} />
      )}
      <Section title="Up for grabs" chores={available.data} empty="No open chores right now." onAction={onAction} busy={act.isPending} />
      {(isAdmin || user?.role === 'viewer') && (
        <Section title="Everyone today" chores={family.data} empty="No chores today." onAction={onAction} busy={act.isPending} />
      )}
    </div>
  )
}
