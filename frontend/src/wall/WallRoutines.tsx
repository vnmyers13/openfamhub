import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { completeWallRoutineStep, useWallRoutines } from '../api/wall'
import { errorDetail } from '../api/client'
import type { RoutineRun } from '../api/chores'
import { routineTimeline } from '../lib/routine'

const HEADS_UP_SECONDS = 30 * 60 // show a routine half an hour before it starts

function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function useTick(ms: number): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}

function RoutineCard({ run, now, timeZone }: { run: RoutineRun; now: Date; timeZone: string }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const complete = useMutation({
    mutationFn: completeWallRoutineStep,
    onSuccess: () => {
      setError('')
      queryClient.invalidateQueries({ queryKey: ['wall-routines'] })
      queryClient.invalidateQueries({ queryKey: ['wall-progress'] })
    },
    onError: (err) => setError(errorDetail(err, 'Could not complete this step.')),
  })
  const t = routineTimeline(now, run.start_time, run.steps, timeZone)
  const done = run.steps.filter((s) => s.status === 'completed').length
  if (!t || t.phase === 'after' || done === run.steps.length) return null
  if (t.phase === 'before' && t.secondsLeft > HEADS_UP_SECONDS) return null
  const step = run.steps[t.index]
  return (
    <div className="rounded-xl bg-slate-800/70 p-4" data-testid="wall-routine">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-lg font-semibold text-white">{run.name}</span>
        <span className="text-sm" style={{ color: run.assigned_color ?? '#94a3b8' }}>{run.assigned_name ?? ''}</span>
      </div>
      {t.phase === 'before' ? (
        <p className="text-slate-300">Starts in {Math.ceil(t.secondsLeft / 60)} min</p>
      ) : (
        <>
          <p className="text-2xl font-bold text-white">{step.title}</p>
          <p className="font-mono text-4xl text-amber-300" aria-label="time left">{clock(t.secondsLeft)}</p>
          {step.status !== 'completed' && (
            <button
              type="button"
              className="mt-3 rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-950 disabled:cursor-wait disabled:bg-slate-500"
              disabled={complete.isPending}
              onClick={() => {
                setError('')
                complete.mutate(step.instance_id)
              }}
            >
              {complete.isPending ? 'Saving…' : `Done with ${step.title}`}
            </button>
          )}
          {error && <p className="mt-2 text-sm text-red-300" role="alert">{error}</p>}
          <div className="mt-2 h-2 overflow-hidden rounded bg-slate-700" aria-label={`${done} of ${run.steps.length} done`}>
            <div className="h-full bg-emerald-400" style={{ width: `${(done / run.steps.length) * 100}%` }} />
          </div>
          <ol className="mt-2 space-y-0.5 text-sm">
            {run.steps.map((s, i) => (
              <li key={s.instance_id} className={s.status === 'completed' ? 'text-slate-500 line-through' : i === t.index ? 'text-white' : 'text-slate-400'}>
                {s.status === 'completed' ? '✓ ' : ''}{s.title}
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  )
}

/** Routines that are on now (or about to start), with the current step's countdown. */
export default function WallRoutines({ timeZone }: { timeZone: string }) {
  const { data: runs = [] } = useWallRoutines()
  const now = useTick(1000)
  return (
    <div className="flex flex-col gap-3">
      {runs.map((r) => <RoutineCard key={r.id} run={r} now={now} timeZone={timeZone} />)}
    </div>
  )
}
