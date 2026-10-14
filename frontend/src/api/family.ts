import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { SleepSchedule } from '../lib/sleep'

/** An extra clock on the wall (Phase 10), e.g. a grandparent abroad. Up to 3. */
export interface WorldClock {
  label: string
  timezone: string
}

export const MAX_CLOCKS = 3

export interface FamilySettings {
  name: string
  timezone: string
  sleep: SleepSchedule
  clocks?: WorldClock[]
}

export function useFamilySettings() {
  return useQuery({
    queryKey: ['family-settings'],
    queryFn: async () => (await apiClient.get('/family')).data as FamilySettings,
  })
}

export function useUpdateFamilySettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: Partial<FamilySettings>) => (await apiClient.patch('/family', data)).data as FamilySettings,
    onSuccess: (data) => qc.setQueryData(['family-settings'], data),
  })
}
