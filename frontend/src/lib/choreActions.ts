import type { ChoreInstance } from '../api/chores'

export type ChoreAction = 'claim' | 'unclaim' | 'complete' | 'undo'

/** The buttons a person gets on one of today's chores (the API enforces the same rules). */
export function choreActions(c: ChoreInstance, user: { id: string; role: string } | null): ChoreAction[] {
  if (!user || user.role === 'viewer') return []
  const admin = user.role === 'admin'
  if (c.status === 'completed') return admin || c.completed_by === user.id || c.assigned_to === user.id || c.claimed_by === user.id ? ['undo'] : []
  if (c.status === 'missed') return []
  if (c.status === 'claimed') {
    const mine = c.claimed_by === user.id
    return mine ? ['complete', 'unclaim'] : admin ? ['complete', 'unclaim'] : []
  }
  if (c.assigned_to) return c.assigned_to === user.id || admin ? ['complete'] : []
  return ['claim', 'complete']
}

