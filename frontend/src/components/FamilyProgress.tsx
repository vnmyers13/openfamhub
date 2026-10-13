import type { ProgressRow } from '../api/rewards'
import Avatar from './Avatar'
import { cn } from '../lib/utils'

/**
 * Per-member stars: points balance, points earned this week, streak and badges.
 * Shared by the dashboard and the wall; the numbers all come from the points
 * ledger on the server.
 */
export default function FamilyProgress({ rows, size = 'normal' }: { rows: ProgressRow[]; size?: 'normal' | 'wall' }) {
  const wall = size === 'wall'
  if (rows.length === 0) {
    return <p className={cn('text-slate-400', wall ? 'text-lg' : 'text-sm')}>No one is earning points yet.</p>
  }
  return (
    <ul className={cn('flex flex-col', wall ? 'gap-4' : 'gap-2')} aria-label="Family progress">
      {rows.map((r) => (
        <li key={r.user_id} className={cn('flex items-center gap-3 rounded-lg bg-slate-700/40', wall ? 'px-4 py-3' : 'px-3 py-2')}>
          <Avatar name={r.display_name} color={r.color_hex} emoji={r.avatar_value} className={wall ? 'h-12 w-12 text-2xl' : 'h-8 w-8 text-base'} />
          <div className="min-w-0 flex-1">
            <p className={cn('truncate font-medium text-white', wall ? 'text-xl' : 'text-sm')}>{r.display_name}</p>
            <p className={cn('text-slate-400', wall ? 'text-base' : 'text-xs')}>
              +{r.points_this_week} this week
              {r.streak_days > 0 && <> · 🔥 {r.streak_days}-day streak</>}
            </p>
            {r.badges.length > 0 && (
              <p className={cn('mt-0.5 truncate', wall ? 'text-xl' : 'text-sm')} aria-label={`Badges: ${r.badges.map((b) => b.name).join(', ')}`}>
                {r.badges.map((b) => <span key={b.id} title={b.name}>{b.icon || '🏅'}</span>)}
              </p>
            )}
          </div>
          <span className={cn('shrink-0 font-bold text-amber-300', wall ? 'text-3xl' : 'text-lg')} aria-label={`${r.points_balance} points`}>
            ⭐ {r.points_balance}
          </span>
        </li>
      ))}
    </ul>
  )
}
