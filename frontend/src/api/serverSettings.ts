import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

/** One server setting as Admin › Settings sees it (backend services/server_config.py). */
export interface PlainSetting { value: string | number; locked: boolean }
/** Secrets are write-only: the API only says whether one is set. */
export interface SecretSetting { is_set: boolean; locked: boolean; unreadable?: boolean }
export type ServerSettings = Record<string, PlainSetting | SecretSetting>
export interface TestResult { ok: boolean; message: string }

export const isSecret = (s: PlainSetting | SecretSetting | undefined): s is SecretSetting => Boolean(s && 'is_set' in s)

export function useServerSettings() {
  return useQuery({
    queryKey: ['server-settings'],
    queryFn: async () => (await apiClient.get('/admin/server-settings')).data as ServerSettings,
  })
}

export function useSaveServerSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (changes: Record<string, string | number>) =>
      (await apiClient.put('/admin/server-settings', changes)).data as ServerSettings,
    onSuccess: (data) => {
      qc.setQueryData(['server-settings'], data)
      void qc.invalidateQueries({ queryKey: ['ha-status'] })
      void qc.invalidateQueries({ queryKey: ['notify-channels'] })
    },
  })
}

export async function testServerSetting(what: 'home-assistant' | 'ntfy' | 'email'): Promise<TestResult> {
  return (await apiClient.post(`/admin/server-settings/test/${what}`)).data as TestResult
}
