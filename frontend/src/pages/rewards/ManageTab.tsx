import { useState } from 'react'
import { useFamilyMembers } from '../../api/chores'
import { errorDetail } from '../../api/client'
import {
  useAdjustPoints, useBadges, useRetireBadge, useRetireReward, useRewardCatalog, useSaveBadge, useSaveReward,
  type Badge, type BadgeKind, type Reward,
} from '../../api/rewards'
import { BADGE_KINDS, describeBadge } from '../../lib/badges'
import { Banner, MemberSelect } from '../chores/Controls'
import { input, primary, subtle } from '../chores/shared'

const label = 'mb-1 block text-xs text-gray-400'
const heading = 'mb-2 text-sm font-semibold uppercase tracking-wider text-gray-400'

function RewardForm({ reward, onDone, onError }: { reward?: Reward; onDone: () => void; onError: (m: string) => void }) {
  const save = useSaveReward()
  const [name, setName] = useState(reward?.name ?? '')
  const [icon, setIcon] = useState(reward?.icon ?? '🎁')
  const [cost, setCost] = useState(reward?.point_cost ?? 20)
  const [approval, setApproval] = useState(reward?.needs_approval ?? false)
  const [description, setDescription] = useState(reward?.description ?? '')
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await save.mutateAsync({ id: reward?.id, name: name.trim(), icon: icon.trim() || null, point_cost: cost,
        needs_approval: approval, description: description.trim() || null })
      onDone()
    } catch (err) {
      onError(errorDetail(err, "Couldn't save the reward"))
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-gray-800 bg-gray-900 p-4" aria-label={reward ? `Edit ${reward.name}` : 'New reward'}>
      <div className="grid gap-3 sm:grid-cols-[4rem_1fr_6rem]">
        <div><label htmlFor="reward-icon" className={label}>Icon</label>
          <input id="reward-icon" className={input} value={icon} maxLength={16} onChange={(e) => setIcon(e.target.value)} /></div>
        <div><label htmlFor="reward-name" className={label}>Reward</label>
          <input id="reward-name" className={input} value={name} maxLength={128} required onChange={(e) => setName(e.target.value)} /></div>
        <div><label htmlFor="reward-cost" className={label}>Points</label>
          <input id="reward-cost" type="number" min={1} className={input} value={cost}
            onChange={(e) => setCost(Math.max(1, Number(e.target.value) || 1))} /></div>
      </div>
      <div><label htmlFor="reward-desc" className={label}>Details (optional)</label>
        <input id="reward-desc" className={input} value={description} maxLength={1000} onChange={(e) => setDescription(e.target.value)} /></div>
      <label className="flex items-center gap-2 text-sm text-gray-300">
        <input type="checkbox" checked={approval} onChange={(e) => setApproval(e.target.checked)} />
        Needs a grown-up's yes (points are held until then)
      </label>
      <div className="flex justify-end gap-2">
        <button type="button" className={subtle} onClick={onDone}>Cancel</button>
        <button type="submit" className={primary} disabled={save.isPending || !name.trim()}>Save reward</button>
      </div>
    </form>
  )
}

function BadgeForm({ badge, onDone, onError }: { badge?: Badge; onDone: () => void; onError: (m: string) => void }) {
  const save = useSaveBadge()
  const [name, setName] = useState(badge?.name ?? '')
  const [icon, setIcon] = useState(badge?.icon ?? '🏅')
  const [kind, setKind] = useState<BadgeKind>(badge?.kind ?? 'chores_completed')
  const [threshold, setThreshold] = useState(badge?.threshold ?? 10)
  const [bonus, setBonus] = useState(badge?.bonus_points ?? 0)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await save.mutateAsync({ id: badge?.id, name: name.trim(), icon: icon.trim() || null, kind, threshold, bonus_points: bonus })
      onDone()
    } catch (err) {
      onError(errorDetail(err, "Couldn't save the badge"))
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-gray-800 bg-gray-900 p-4" aria-label={badge ? `Edit ${badge.name}` : 'New badge'}>
      <div className="grid gap-3 sm:grid-cols-[4rem_1fr]">
        <div><label htmlFor="badge-icon" className={label}>Icon</label>
          <input id="badge-icon" className={input} value={icon} maxLength={16} onChange={(e) => setIcon(e.target.value)} /></div>
        <div><label htmlFor="badge-name" className={label}>Badge</label>
          <input id="badge-name" className={input} value={name} maxLength={64} required onChange={(e) => setName(e.target.value)} /></div>
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_6rem_6rem]">
        <div><label htmlFor="badge-kind" className={label}>Earned by</label>
          <select id="badge-kind" className={input} value={kind} onChange={(e) => setKind(e.target.value as BadgeKind)}>
            {BADGE_KINDS.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
          </select></div>
        <div><label htmlFor="badge-threshold" className={label}>Reach</label>
          <input id="badge-threshold" type="number" min={1} className={input} value={threshold}
            onChange={(e) => setThreshold(Math.max(1, Number(e.target.value) || 1))} /></div>
        <div><label htmlFor="badge-bonus" className={label}>Bonus pts</label>
          <input id="badge-bonus" type="number" min={0} className={input} value={bonus}
            onChange={(e) => setBonus(Math.max(0, Number(e.target.value) || 0))} /></div>
      </div>
      <p className="text-xs text-gray-500">{describeBadge(kind, threshold)}. Anyone who already qualifies gets it right away.</p>
      <div className="flex justify-end gap-2">
        <button type="button" className={subtle} onClick={onDone}>Cancel</button>
        <button type="submit" className={primary} disabled={save.isPending || !name.trim()}>Save badge</button>
      </div>
    </form>
  )
}

function PointsAdjust({ onError }: { onError: (m: string) => void }) {
  const { data: members } = useFamilyMembers()
  const adjust = useAdjustPoints()
  const [who, setWho] = useState<string | null>(null)
  const [delta, setDelta] = useState(5)
  const [reason, setReason] = useState('')
  const [done, setDone] = useState<string | null>(null)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!who) return
    setDone(null)
    try {
      await adjust.mutateAsync({ user_id: who, delta, reason: reason.trim() })
      setDone(`${delta > 0 ? 'Added' : 'Took away'} ${Math.abs(delta)} points.`)
      setReason('')
    } catch (err) {
      onError(errorDetail(err, "Couldn't change the points"))
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-gray-800 bg-gray-900 p-4" aria-label="Adjust points">
      <div className="grid gap-3 sm:grid-cols-[10rem_6rem_1fr]">
        <div><label htmlFor="adjust-who" className={label}>Who</label>
          <MemberSelect id="adjust-who" value={who} onChange={setWho} members={members} anyoneLabel="Choose…" /></div>
        <div><label htmlFor="adjust-delta" className={label}>Points (±)</label>
          <input id="adjust-delta" type="number" className={input} value={delta} onChange={(e) => setDelta(Math.trunc(Number(e.target.value) || 0))} /></div>
        <div><label htmlFor="adjust-reason" className={label}>Why</label>
          <input id="adjust-reason" className={input} value={reason} maxLength={256} required onChange={(e) => setReason(e.target.value)} /></div>
      </div>
      <div className="flex items-center justify-end gap-3">
        {done && <span className="text-sm text-emerald-300" role="status">{done}</span>}
        <button type="submit" className={primary} disabled={adjust.isPending || !who || !delta || !reason.trim()}>Change points</button>
      </div>
    </form>
  )
}

export default function ManageTab() {
  const { data: rewards } = useRewardCatalog(true)
  const { data: badges } = useBadges(true)
  const retireReward = useRetireReward()
  const saveReward = useSaveReward()
  const retireBadge = useRetireBadge()
  const [editing, setEditing] = useState<string | null>(null) // 'new-reward', 'new-badge', 'reward:<id>', 'badge:<id>'
  const [error, setError] = useState<string | null>(null)
  const close = () => setEditing(null)
  const run = async (fn: () => Promise<unknown>, fallback: string) => {
    try { await fn() } catch (err) { setError(errorDetail(err, fallback)) }
  }
  return (
    <div className="space-y-8">
      <Banner text={error} onClose={() => setError(null)} />
      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className={heading}>Rewards</h2>
          <button className={subtle} onClick={() => setEditing('new-reward')}>+ Reward</button>
        </div>
        {editing === 'new-reward' && <RewardForm onDone={close} onError={setError} />}
        <ul className="mt-2 space-y-2">
          {(rewards ?? []).map((r) => editing === `reward:${r.id}` ? <li key={r.id}><RewardForm reward={r} onDone={close} onError={setError} /></li> : (
            <li key={r.id} className={`flex items-center justify-between gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-2 ${r.is_active ? '' : 'opacity-50'}`}>
              <span className="text-white">{r.icon} {r.name} <span className="text-sm text-amber-300">⭐ {r.point_cost}</span>
                {r.needs_approval && <span className="ml-2 text-xs text-gray-400">needs a yes</span>}
                {!r.is_active && <span className="ml-2 text-xs text-gray-400">retired</span>}</span>
              <span className="flex shrink-0 gap-2">
                <button className={subtle} onClick={() => setEditing(`reward:${r.id}`)} aria-label={`Edit: ${r.name}`}>Edit</button>
                {r.is_active
                  ? <button className={subtle} onClick={() => run(() => retireReward.mutateAsync(r.id), "Couldn't retire the reward")} aria-label={`Retire: ${r.name}`}>Retire</button>
                  : <button className={subtle} onClick={() => run(() => saveReward.mutateAsync({ id: r.id, is_active: true }), "Couldn't bring the reward back")} aria-label={`Bring back: ${r.name}`}>Bring back</button>}
              </span>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className={heading}>Badges</h2>
          <button className={subtle} onClick={() => setEditing('new-badge')}>+ Badge</button>
        </div>
        {editing === 'new-badge' && <BadgeForm onDone={close} onError={setError} />}
        <ul className="mt-2 space-y-2">
          {(badges ?? []).map((b) => editing === `badge:${b.id}` ? <li key={b.id}><BadgeForm badge={b} onDone={close} onError={setError} /></li> : (
            <li key={b.id} className={`flex items-center justify-between gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-2 ${b.is_active ? '' : 'opacity-50'}`}>
              <span className="text-white">{b.icon} {b.name} <span className="text-sm text-gray-400">· {describeBadge(b.kind, b.threshold)}
                {b.bonus_points > 0 && ` · +${b.bonus_points}`}{!b.is_active && ' · retired'}</span></span>
              <span className="flex shrink-0 gap-2">
                <button className={subtle} onClick={() => setEditing(`badge:${b.id}`)} aria-label={`Edit: ${b.name}`}>Edit</button>
                {b.is_active && <button className={subtle} onClick={() => run(() => retireBadge.mutateAsync(b.id), "Couldn't retire the badge")} aria-label={`Retire: ${b.name}`}>Retire</button>}
              </span>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className={heading}>Give or take points</h2>
        <PointsAdjust onError={setError} />
      </section>
    </div>
  )
}
