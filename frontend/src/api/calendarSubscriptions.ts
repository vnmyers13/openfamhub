import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

export type SubscriptionKind = 'titles' | 'full'

export interface CalendarSubscriptionListItem {
  id: string
  family_id: string
  kind: SubscriptionKind
  active: boolean
  last_published_at: string | null
  last_error: string | null
}

export interface CalendarSubscriptionDetailItem extends CalendarSubscriptionListItem {
  subscription_url: string
}

export interface AuditLogEntry {
  id: string
  subscription_id: string
  family_id: string
  action: 'created' | 'revealed' | 'rotated' | 'revoked'
  actor_user_id: string
  created_at: string
}

export function useCalendarSubscriptions() {
  return useQuery({
    queryKey: ['calendar-subscriptions'],
    queryFn: async () => {
      const res = await apiClient.get('/calendar/subscriptions')
      return res.data as CalendarSubscriptionListItem[]
    },
  })
}

/** Create or recreate a subscription of the given kind. Returns the URL. */
export function useCreateCalendarSubscription() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (kind: SubscriptionKind) => {
      const res = await apiClient.post(`/calendar/subscriptions/${kind}`)
      return res.data as CalendarSubscriptionDetailItem
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-subscriptions'] })
    },
  })
}

/** Reveal the URL for an existing subscription. */
export function useRevealCalendarSubscription() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (kind: SubscriptionKind) => {
      const res = await apiClient.post(`/calendar/subscriptions/${kind}/reveal`)
      return res.data as CalendarSubscriptionDetailItem
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-subscriptions'] })
    },
  })
}

/** Rotate the relay feed, returning the new URL. */
export function useRotateCalendarSubscription() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (kind: SubscriptionKind) => {
      const res = await apiClient.post(`/calendar/subscriptions/${kind}/rotate`)
      return res.data as CalendarSubscriptionDetailItem
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-subscriptions'] })
    },
  })
}

/** Revoke (disable) a subscription. */
export function useRevokeCalendarSubscription() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (kind: SubscriptionKind) => {
      await apiClient.delete(`/calendar/subscriptions/${kind}`)
      return { ok: true }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-subscriptions'] })
    },
  })
}

/** Fetch audit log entries for all subscriptions in the family. */
export function useSubscriptionAuditLog() {
  return useQuery({
    queryKey: ['calendar-subscriptions-audit-log'],
    queryFn: async () => {
      const res = await apiClient.get('/calendar/subscriptions/audit-log')
      return res.data as AuditLogEntry[]
    },
  })
}
