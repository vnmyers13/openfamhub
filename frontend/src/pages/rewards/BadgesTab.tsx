import { useBadges, useFamilyProgress } from '../../api/rewards'
import { describeBadge } from '../../lib/badges'
import { useAuthStore } from '../../stores/auth'

export default function BadgesTab() {
  const user = useAuthStore((s) => s.user)
  const { data: badges } = useBadges()
  const { data: progress } = useFamilyProgress()
  const mine = new Set(progress?.find((r) => r.user_id === user?.id)?.badges.map((b) => b.id))
  return (
    <div>
      {badges && badges.length === 0 && <p className="text-sm text-gray-500">No badges yet.</p>}
      <ul className="grid gap-3 sm:grid-cols-2">
        {(badges ?? []).map((b) => {
          const earned = mine.has(b.id)
          return (
            <li key={b.id} className={`flex items-center gap-3 rounded-lg border p-4 ${earned ? 'border-amber-500/50 bg-amber-900/20' : 'border-gray-800 bg-gray-900'}`}>
              <span className={`text-3xl ${earned ? '' : 'opacity-40 grayscale'}`} aria-hidden="true">{b.icon || '🏅'}</span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-white">{b.name}{earned && <span className="ml-2 text-xs text-amber-300">Earned</span>}</p>
                <p className="text-sm text-gray-400">
                  {describeBadge(b.kind, b.threshold)}{b.bonus_points > 0 && ` · +${b.bonus_points} bonus`}
                </p>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
