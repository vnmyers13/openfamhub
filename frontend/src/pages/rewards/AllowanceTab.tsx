import { useState } from 'react'
import { errorDetail } from '../../api/client'
import { useAdjustAllowance, useAllowance, useAllowanceHistory, useSetAllowance, type AllowanceRow } from '../../api/rewards'
import { formatCents, parseDollars } from '../../lib/money'
import { useAuthStore } from '../../stores/auth'
import { Banner } from '../chores/Controls'
import { input, subtle } from '../chores/shared'

function nextPayout(row: AllowanceRow): string {
  if (!row.next_payout) return 'No weekly allowance'
  const day = new Date(`${row.next_payout}T00:00:00`)
  return `${formatCents(row.weekly_cents)} every Monday · next ${day.toLocaleDateString([], { month: 'short', day: 'numeric' })}`
}

function History({ userId }: { userId: string }) {
  const { data } = useAllowanceHistory(userId)
  if (data && data.length === 0) return <p className="text-sm text-gray-500">Nothing yet.</p>
  return (
    <ul className="space-y-1">
      {(data ?? []).map((e) => (
        <li key={e.id} className="flex justify-between gap-2 text-sm text-gray-300">
          <span className="truncate">{e.reason}</span>
          <span className={e.delta_cents < 0 ? 'text-red-300' : 'text-emerald-300'}>{formatCents(e.delta_cents)}</span>
        </li>
      ))}
    </ul>
  )
}

function AdminRow({ row, onError }: { row: AllowanceRow; onError: (m: string) => void }) {
  const setAllowance = useSetAllowance()
  const adjust = useAdjustAllowance()
  const [weekly, setWeekly] = useState((row.weekly_cents / 100).toFixed(2))
  const [payout, setPayout] = useState('')
  const [open, setOpen] = useState(false)
  const name = row.display_name

  const saveWeekly = async () => {
    const cents = parseDollars(weekly)
    if (cents === null) return onError('Enter an amount like 5 or 5.50')
    try {
      await setAllowance.mutateAsync({ userId: row.user_id, weekly_cents: cents })
    } catch (err) {
      onError(errorDetail(err, "Couldn't save the allowance"))
    }
  }
  const recordPayout = async (e: React.FormEvent) => {
    e.preventDefault()
    const cents = parseDollars(payout)
    if (!cents) return onError('Enter the amount you paid, like 5 or 5.50')
    try {
      await adjust.mutateAsync({ userId: row.user_id, delta_cents: -cents, reason: 'Paid out' })
      setPayout('')
    } catch (err) {
      onError(errorDetail(err, "Couldn't record the payout"))
    }
  }
  return (
    <li className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-medium text-white">{name}</p>
          <p className="text-xs text-gray-400">{nextPayout(row)}</p>
        </div>
        <p className="text-xl font-semibold text-emerald-300" aria-label={`${name} balance`}>{formatCents(row.balance_cents)}</p>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <div className="flex items-end gap-2">
          <div>
            <label htmlFor={`weekly-${row.user_id}`} className="mb-1 block text-xs text-gray-400">Weekly ($)</label>
            <input id={`weekly-${row.user_id}`} className={`${input} w-24`} inputMode="decimal" value={weekly}
              onChange={(e) => setWeekly(e.target.value)} aria-label={`Weekly allowance for ${name}`} />
          </div>
          <button className={subtle} disabled={setAllowance.isPending} onClick={saveWeekly} aria-label={`Save weekly allowance for ${name}`}>Save</button>
        </div>
        <form className="flex items-end gap-2" onSubmit={recordPayout}>
          <div>
            <label htmlFor={`payout-${row.user_id}`} className="mb-1 block text-xs text-gray-400">Paid out ($)</label>
            <input id={`payout-${row.user_id}`} className={`${input} w-24`} inputMode="decimal" value={payout}
              onChange={(e) => setPayout(e.target.value)} aria-label={`Amount paid to ${name}`} />
          </div>
          <button type="submit" className={subtle} disabled={adjust.isPending || !payout.trim()} aria-label={`Record payout to ${name}`}>Record</button>
        </form>
        <button className={subtle} onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? 'Hide history' : 'History'}</button>
      </div>
      {open && <div className="mt-3"><History userId={row.user_id} /></div>}
    </li>
  )
}

export default function AllowanceTab() {
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin'
  const { data: rows } = useAllowance()
  const [error, setError] = useState<string | null>(null)

  if (isAdmin) {
    return (
      <div>
        <Banner text={error} onClose={() => setError(null)} />
        <p className="mb-4 text-sm text-gray-400">Allowance is paid into each balance every Monday at 7:00. Record cash you hand over so the balance stays right.</p>
        <ul className="space-y-3">
          {(rows ?? []).map((r) => <AdminRow key={r.user_id} row={r} onError={setError} />)}
        </ul>
      </div>
    )
  }
  const me = rows?.[0]
  if (!me) return rows ? <p className="text-sm text-gray-500">No allowance.</p> : null
  return (
    <div className="grid gap-6 md:grid-cols-[16rem_1fr]">
      <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-center">
        <p className="text-xs uppercase tracking-wider text-gray-400">My allowance</p>
        <p className="text-3xl font-bold text-emerald-300">{formatCents(me.balance_cents)}</p>
        <p className="mt-1 text-xs text-gray-400">{nextPayout(me)}</p>
      </div>
      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400">History</h2>
        <History userId={me.user_id} />
      </section>
    </div>
  )
}
