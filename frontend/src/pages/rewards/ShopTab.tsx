import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { useFamilyProgress, usePointsHistory, useRedeem, useRewardCatalog, type Reward } from '../../api/rewards'
import { useAuthStore } from '../../stores/auth'
import { Banner } from '../chores/Controls'
import { primary } from '../chores/shared'

export default function ShopTab() {
  const user = useAuthStore((s) => s.user)
  const canSpend = !!user && user.role !== 'viewer'
  const { data: rewards } = useRewardCatalog()
  const { data: progress } = useFamilyProgress()
  const me = progress?.find((r) => r.user_id === user?.id)
  const balance = me?.points_balance ?? 0
  const redeem = useRedeem()
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const onRedeem = async (r: Reward) => {
    setError(null)
    setDone(null)
    try {
      await redeem.mutateAsync(r.id)
      setDone(r.needs_approval ? `Asked for ${r.name}. A grown-up will say yes or no.` : `${r.name} is yours!`)
    } catch (err) {
      setError(errorDetail(err, "Couldn't get that reward"))
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_16rem]">
      <section>
        <Banner text={error} onClose={() => setError(null)} />
        {done && <p className="mb-4 rounded bg-emerald-900/40 px-4 py-2 text-sm text-emerald-200" role="status">{done}</p>}
        {rewards && rewards.length === 0 && <p className="text-sm text-gray-500">No rewards yet.</p>}
        <ul className="grid gap-3 sm:grid-cols-2">
          {(rewards ?? []).map((r) => {
            const short = r.point_cost - balance
            return (
              <li key={r.id} className="flex flex-col gap-2 rounded-lg border border-gray-800 bg-gray-900 p-4">
                <div className="flex items-start gap-3">
                  <span className="text-3xl" aria-hidden="true">{r.icon || '🎁'}</span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-white">{r.name}</p>
                    {r.description && <p className="text-sm text-gray-400">{r.description}</p>}
                  </div>
                  <span className="shrink-0 font-semibold text-amber-300">⭐ {r.point_cost}</span>
                </div>
                {canSpend && (
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-gray-500">{short > 0 ? `${short} more to go` : r.needs_approval ? 'Needs a yes from a grown-up' : ''}</span>
                    <button className={primary} disabled={short > 0 || redeem.isPending} onClick={() => onRedeem(r)}
                      aria-label={`${r.needs_approval ? 'Ask for' : 'Get'}: ${r.name}`}>
                      {r.needs_approval ? 'Ask for it' : 'Get it'}
                    </button>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </section>
      {canSpend && <MyPoints balance={balance} />}
    </div>
  )
}

function MyPoints({ balance }: { balance: number }) {
  const { data: history } = usePointsHistory()
  return (
    <aside>
      <div className="mb-4 rounded-lg border border-gray-800 bg-gray-900 p-4 text-center">
        <p className="text-xs uppercase tracking-wider text-gray-400">My points</p>
        <p className="text-3xl font-bold text-amber-300">⭐ {balance}</p>
      </div>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">Recent</h2>
      {history && history.length === 0 && <p className="text-sm text-gray-500">Nothing yet.</p>}
      <ul className="space-y-1">
        {(history ?? []).slice(0, 10).map((h) => (
          <li key={h.id} className="flex justify-between gap-2 text-sm text-gray-300">
            <span className="truncate">{h.reason}</span>
            <span className={h.delta < 0 ? 'text-red-300' : 'text-emerald-300'}>{h.delta > 0 ? `+${h.delta}` : h.delta}</span>
          </li>
        ))}
      </ul>
    </aside>
  )
}
