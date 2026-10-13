import type { BadgeKind } from '../api/rewards'

export const BADGE_KINDS: { kind: BadgeKind; label: string }[] = [
  { kind: 'chores_completed', label: 'Chores completed' },
  { kind: 'streak_days', label: 'Day streak' },
  { kind: 'points_earned', label: 'Chore points earned' },
]

/** What earns a badge, in words: "Complete 10 chores", "A 7-day streak", "Earn 100 chore points". */
export function describeBadge(kind: BadgeKind, threshold: number): string {
  if (kind === 'streak_days') return `A ${threshold}-day streak`
  if (kind === 'chores_completed') return `Complete ${threshold} chore${threshold === 1 ? '' : 's'}`
  return `Earn ${threshold} chore point${threshold === 1 ? '' : 's'}`
}
