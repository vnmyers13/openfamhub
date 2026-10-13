import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { useChoreAction, useTodayRoutines } from '../../api/chores'
import { useAuthStore } from '../../stores/auth'
import { Banner } from './Controls'

/** Today's routines: tick steps off in order (each is a chore underneath). */
export default function RoutinesTab() {
  const user = useAuthStore((s) => s.user)
  const { data: runs } = useTodayRoutines()
  const act = useChoreAction()
  const [error, setError] = useState<string | null>(null)
  const canTick = (assignee: string | null) =>
    !!user && user.role !== 'viewer' && (user.role === 'admin' || !assignee || assignee === user.id)

  if (runs && runs.length === 0) return <p className="text-sm text-gray-500">No routines today.</p>
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="md:col-span-2"><Banner text={error} onClose={() => setError(null)} /></div>
      {(runs ?? []).map((run) => {
        const done = run.steps.filter((s) => s.status === 'completed').length
        return (
          <section key={run.id} className="rounded-lg border border-gray-800 bg-gray-900 p-4">
            <div className="mb-3 flex items-baseline justify-between gap-2">
              <h2 className="font-semibold text-white">{run.name}</h2>
              <span className="text-xs text-gray-400">
                {run.assigned_name ?? 'Anyone'}{run.start_time ? ` · ${run.start_time}` : ''} · {done}/{run.steps.length}
              </span>
            </div>
            <ol className="space-y-2">
              {run.steps.map((s) => {
                const checked = s.status === 'completed'
                return (
                  <li key={s.instance_id} className="flex items-center gap-3">
                    <input type="checkbox" checked={checked} aria-label={`${s.title} done`}
                      disabled={!canTick(run.assigned_to) || s.status === 'missed' || act.isPending}
                      onChange={async () => {
                        setError(null)
                        try {
                          await act.mutateAsync({ id: s.instance_id, action: checked ? 'undo' : 'complete' })
                        } catch (err) {
                          setError(errorDetail(err, "That didn't work"))
                        }
                      }} />
                    <span className={checked ? 'text-gray-500 line-through' : 'text-gray-200'}>{s.title}</span>
                    <span className="ml-auto text-xs text-gray-500">{s.minutes} min</span>
                  </li>
                )
              })}
            </ol>
          </section>
        )
      })}
    </div>
  )
}
