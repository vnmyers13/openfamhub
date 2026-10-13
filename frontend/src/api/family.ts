import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { SleepSchedule } from '../lib/sleep'

export interface FamilySettings {
  name: string
  timezone: string
  sleep: SleepSchedule
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
