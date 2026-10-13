import { useState } from 'react'
import { useFamilyMembers } from '../../api/chores'
import { errorDetail } from '../../api/client'
import { useDecide, useRedemptions, type Redemption } from '../../api/rewards'
import { useAuthStore } from '../../stores/auth'
import { Banner } from '../chores/Controls'
import { input, nameOf, primary, subtle } from '../chores/shared'

const STATUS: Record<Redemption['status'], string> = {
  pending: 'Waiting', approved: 'Yes', rejected: 'No', cancelled: 'Cancelled',
}

export default function RequestsTab() {
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin'
  const { data: requests } = useRedemptions()
  const { data: members } = useFamilyMembers()
  const decide = useDecide()
  const [error, setError] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState<string | null>(null)
  const [note, setNote] = useState('')

  const act = async (id: string, action: 'approve' | 'reject' | 'cancel', why?: string) => {
    setError(null)
    try {
      await decide.mutateAsync({ id, action, note: why })
      setRejecting(null)
      setNote('')
    } catch (err) {
      setError(errorDetail(err, "Couldn't update the request"))
    }
  }

  const waiting = isAdmin ? (requests ?? []).filter((r) => r.status === 'pending') : []
  const rest = isAdmin ? (requests ?? []).filter((r) => r.status !== 'pending') : requests ?? []

  return (
    <div>
      <Banner text={error} onClose={() => setError(null)} />
      {isAdmin && (
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">Waiting for you</h2>
          {waiting.length === 0 && <p className="text-sm text-gray-500">Nothing to decide.</p>}
          <ul className="space-y-2">
            {waiting.map((r) => (
              <li key={r.id} className="rounded-lg border border-gray-800 bg-gray-900 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-white">{nameOf(members, r.user_id)} wants <b>{r.reward_name}</b> <span className="text-amber-300">⭐ {r.point_cost}</span></span>
                  <span className="flex shrink-0 gap-2">
                    <button className={primary} disabled={decide.isPending} onClick={() => act(r.id, 'approve')} aria-label={`Approve: ${r.reward_name}`}>Yes</button>
                    <button className={subtle} disabled={decide.isPending} onClick={() => setRejecting(r.id)} aria-label={`Reject: ${r.reward_name}`}>No</button>
                  </span>
                </div>
                {rejecting === r.id && (
                  <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); act(r.id, 'reject', note.trim()) }}>
                    <input className={input} aria-label="Reason (optional)" placeholder="Reason (optional)" maxLength={256}
                      value={note} onChange={(e) => setNote(e.target.value)} />
                    <button type="submit" className={primary} disabled={decide.isPending}>Say no</button>
                    <button type="button" className={subtle} onClick={() => setRejecting(null)}>Cancel</button>
                  </form>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">{isAdmin ? 'Recent' : 'My requests'}</h2>
        {requests && rest.length === 0 && <p className="text-sm text-gray-500">Nothing yet.</p>}
        <ul className="space-y-1">
          {rest.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-3 rounded border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200">
              <span className="min-w-0 truncate">
                {r.reward_name}{isAdmin && <> — {nameOf(members, r.user_id)}</>}
                {r.note && <span className="text-gray-500"> · {r.note}</span>}
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="text-gray-400">{STATUS[r.status]}</span>
                {r.status === 'pending' && r.user_id === user?.id && (
                  <button className={subtle} disabled={decide.isPending} onClick={() => act(r.id, 'cancel')} aria-label={`Cancel: ${r.reward_name}`}>Cancel</button>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
