/**
 * Client-side mirrors of the API's event rules, used to hide controls the
 * server would refuse. The server still enforces them.
 */
type Who = { id: string; role: string } | null | undefined

/** Viewers are read-only; admins and members can add events. */
export function canCreateEvents(user: Who): boolean {
  return !!user && (user.role === 'admin' || user.role === 'member')
}

/**
 * Subscribed-calendar events are read-only, viewers can't change anything,
 * members change their own events, admins any.
 */
export function canEditEvent(user: Who, event: { createdBy: string | null; synced: boolean }): boolean {
  if (!user || event.synced || user.role === 'viewer') return false
  return user.role === 'admin' || event.createdBy === user.id
}
