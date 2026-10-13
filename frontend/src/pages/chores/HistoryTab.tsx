import { useChoreLog, useFamilyMembers, useFamilyPoints } from '../../api/chores'
import { nameOf } from './shared'

export default function HistoryTab() {
  const { data: points } = useFamilyPoints()
  const { data: log } = useChoreLog()
  const { data: members } = useFamilyMembers()
  return (
    <div className="grid gap-6 md:grid-cols-[16rem_1fr]">
      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">Points</h2>
        <ul className="space-y-1 rounded-lg border border-gray-800 bg-gray-900 p-3">
          {(points ?? []).map((p) => (
            <li key={p.user_id} className="flex justify-between text-sm text-gray-200">
              <span>{p.display_name}</span><span className="font-semibold">{p.points}</span>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">Done recently</h2>
        {log && log.length === 0 && <p className="text-sm text-gray-500">Nothing yet.</p>}
        <ul className="space-y-1">
          {(log ?? []).map((e) => (
            <li key={e.id} className={`flex justify-between gap-3 rounded border border-gray-800 bg-gray-900 px-3 py-2 text-sm ${e.undone_at ? 'text-gray-500 line-through' : 'text-gray-200'}`}>
              <span>{e.title} — {nameOf(members, e.credited_to ?? e.completed_by)}</span>
              <span className="shrink-0 text-gray-400">
                +{e.points} · {new Date(e.completed_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
