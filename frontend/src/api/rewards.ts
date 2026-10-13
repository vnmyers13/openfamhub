import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

export interface Reward {
  id: string
  name: string
  description: string | null
  icon: string | null
  point_cost: number
  needs_approval: boolean
  is_active: boolean
}

export type RedemptionStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'

export interface Redemption {
  id: string
  reward_id: string
  user_id: string
  reward_name: string
  point_cost: number
  status: RedemptionStatus
  note: string | null
  requested_at: string
  decided_at: string | null
  decided_by: string | null
}

export type BadgeKind = 'streak_days' | 'chores_completed' | 'points_earned'

export interface Badge {
  id: string
  name: string
  description: string | null
  icon: string | null
  kind: BadgeKind
  threshold: number
  bonus_points: number
  is_active: boolean
}

export interface ProgressRow {
  user_id: string
  display_name: string
  color_hex: string
  avatar_value: string | null
  points_balance: number
  points_this_week: number
  streak_days: number
  badges: { id: string; name: string; icon: string | null }[]
}

export interface LedgerEntry { id: string; delta: number; reason: string; source_type: string; created_at: string }

export interface AllowanceRow {
  user_id: string
  display_name: string
  weekly_cents: number
  balance_cents: number
  next_payout: string | null
}

export interface AllowanceEntry {
  id: string
  delta_cents: number
  reason: string
  source_type: string
  week_start: string | null
  created_at: string
}

const get = async <T,>(url: string, params?: object) => (await apiClient.get(url, { params })).data as T

/** Everything a points or rewards change can make stale, including the chores page's balances. */
const REWARD_KEYS = [['reward-catalog'], ['redemptions'], ['badges'], ['progress'], ['points-history'],
  ['allowance'], ['allowance-history'], ['chore-stats'], ['chore-points']]

function useInvalidateRewards() {
  const qc = useQueryClient()
  return () => Promise.all(REWARD_KEYS.map((queryKey) => qc.invalidateQueries({ queryKey })))
}

function useRewardsMutation<V>(fn: (v: V) => Promise<unknown>) {
  const invalidate = useInvalidateRewards()
  return useMutation({ mutationFn: fn, onSettled: invalidate })
}

export function useFamilyProgress() {
  return useQuery({ queryKey: ['progress'], queryFn: () => get<ProgressRow[]>('/rewards/progress') })
}

export function useRewardCatalog(includeInactive = false) {
  return useQuery({
    queryKey: ['reward-catalog', includeInactive],
    queryFn: () => get<Reward[]>('/rewards/catalog', includeInactive ? { include_inactive: true } : undefined),
  })
}

export type RewardInput = Partial<Pick<Reward, 'name' | 'description' | 'icon' | 'point_cost' | 'needs_approval' | 'is_active'>>

export function useSaveReward() {
  return useRewardsMutation(async ({ id, ...data }: RewardInput & { id?: string }) =>
    (id ? await apiClient.patch(`/rewards/catalog/${id}`, data) : await apiClient.post('/rewards/catalog', data)).data as Reward)
}

export function useRetireReward() {
  return useRewardsMutation(async (id: string) => apiClient.delete(`/rewards/catalog/${id}`))
}

export function useRedeem() {
  return useRewardsMutation(async (rewardId: string) =>
    (await apiClient.post(`/rewards/catalog/${rewardId}/redeem`)).data as Redemption)
}

export function useRedemptions(params: { status?: RedemptionStatus } = {}) {
  return useQuery({ queryKey: ['redemptions', params], queryFn: () => get<Redemption[]>('/rewards/redemptions', params) })
}

export function useDecide() {
  return useRewardsMutation(async ({ id, action, note }: { id: string; action: 'approve' | 'reject' | 'cancel'; note?: string }) =>
    (await apiClient.post(`/rewards/redemptions/${id}/${action}`, action === 'reject' ? { note: note || null } : undefined)).data as Redemption)
}

export function usePointsHistory(userId?: string) {
  return useQuery({
    queryKey: ['points-history', userId ?? 'me'],
    queryFn: () => get<LedgerEntry[]>('/rewards/points/history', userId ? { user_id: userId } : undefined),
  })
}

export function useAdjustPoints() {
  return useRewardsMutation(async (body: { user_id: string; delta: number; reason: string }) =>
    (await apiClient.post('/rewards/points/adjust', body)).data as LedgerEntry)
}

export function useBadges(includeInactive = false) {
  return useQuery({
    queryKey: ['badges', includeInactive],
    queryFn: () => get<Badge[]>('/rewards/badges', includeInactive ? { include_inactive: true } : undefined),
  })
}

export type BadgeInput = Partial<Omit<Badge, 'id'>>

export function useSaveBadge() {
  return useRewardsMutation(async ({ id, ...data }: BadgeInput & { id?: string }) =>
    (id ? await apiClient.patch(`/rewards/badges/${id}`, data) : await apiClient.post('/rewards/badges', data)).data as Badge)
}

export function useRetireBadge() {
  return useRewardsMutation(async (id: string) => apiClient.delete(`/rewards/badges/${id}`))
}

export function useAllowance() {
  return useQuery({ queryKey: ['allowance'], queryFn: () => get<AllowanceRow[]>('/rewards/allowance') })
}

export function useAllowanceHistory(userId: string | undefined) {
  return useQuery({
    queryKey: ['allowance-history', userId],
    queryFn: () => get<AllowanceEntry[]>(`/rewards/allowance/${userId}/history`),
    enabled: !!userId,
  })
}

export function useSetAllowance() {
  return useRewardsMutation(async ({ userId, weekly_cents }: { userId: string; weekly_cents: number }) =>
    (await apiClient.put(`/rewards/allowance/${userId}`, { weekly_cents })).data as AllowanceRow)
}

export function useAdjustAllowance() {
  return useRewardsMutation(async ({ userId, delta_cents, reason }: { userId: string; delta_cents: number; reason: string }) =>
    (await apiClient.post(`/rewards/allowance/${userId}/adjust`, { delta_cents, reason })).data as AllowanceEntry)
}
