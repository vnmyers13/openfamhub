import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

/** Phase 12: the family's Home Assistant (backend routers/home_assistant.py). */
export interface HAEntity {
  entity_id: string
  name: string
  domain: string
  state: string
  unit?: string
  device_class?: string
  brightness?: number  // lights, 0-100
  dimmable?: boolean
  hvac_modes?: string[]  // climate
  current_temperature?: number  // climate
  target_temperature?: number
  min_temp?: number
  max_temp?: number
}
export interface HAStates { configured: boolean; available: boolean; error: string | null; entities: HAEntity[] }
export interface HAStatus { configured: boolean; reachable: boolean; error: string | null }
export interface HAConfig { entities: string[]; routine_scenes: Record<string, string> }
export type HAActionName = 'toggle' | 'turn_on' | 'turn_off' | 'set_temperature' | 'set_brightness' | 'set_hvac_mode'
export interface HAActionExtra { temperature?: number; brightness?: number; hvac_mode?: string }
export interface HAHistory { entity_id: string; unit?: string | null; points: [string, number][]; low: number | null; high: number | null }

export const SWITCHABLE = new Set(['light', 'switch', 'fan', 'input_boolean'])
export const RUNNABLE = new Set(['scene', 'script'])

export const DOMAIN_LABEL: Record<string, string> = {
  light: 'Lights', switch: 'Switches', fan: 'Fans', input_boolean: 'Toggles', scene: 'Scenes', script: 'Scripts',
  climate: 'Thermostats', sensor: 'Sensors', binary_sensor: 'Door, window and motion sensors',
}

const STATE_POLL = 30_000

export function useHAStates() {
  return useQuery({
    queryKey: ['ha-states'],
    queryFn: async () => (await apiClient.get('/ha/states')).data as HAStates,
    refetchInterval: STATE_POLL,
  })
}

/** The wall's read-only copy (paired-device cookie). */
export function useWallHAStates() {
  return useQuery({
    queryKey: ['wall-ha-states'],
    queryFn: async () => (await apiClient.get('/wall/home-assistant')).data as HAStates,
    refetchInterval: STATE_POLL,
  })
}

export function useHAAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { entity_id: string; action: HAActionName } & HAActionExtra) =>
      (await apiClient.post('/ha/action', body)).data as HAEntity,
    onSuccess: (entity) => {
      qc.setQueryData<HAStates>(['ha-states'], (old) =>
        old ? { ...old, entities: old.entities.map((e) => (e.entity_id === entity.entity_id ? entity : e)) } : old)
    },
  })
}

/** A sensor's last day (`wall`: through the paired display's endpoint). */
export function useHAHistory(entityId: string, wall = false) {
  return useQuery({
    queryKey: [wall ? 'wall-ha-history' : 'ha-history', entityId],
    queryFn: async () => (await apiClient.get(`${wall ? '/wall/home-assistant' : '/ha'}/history/${entityId}`)).data as HAHistory,
    refetchInterval: 10 * 60_000,
    staleTime: 5 * 60_000,
  })
}

export const HVAC_LABEL: Record<string, string> = {
  off: 'Off', heat: 'Heat', cool: 'Cool', auto: 'Auto', heat_cool: 'Heat/cool', dry: 'Dry', fan_only: 'Fan',
}

export function useHAStatus() {
  return useQuery({ queryKey: ['ha-status'], queryFn: async () => (await apiClient.get('/ha/status')).data as HAStatus })
}

export function useHAEntities(enabled: boolean) {
  return useQuery({
    queryKey: ['ha-entities'],
    queryFn: async () => (await apiClient.get('/ha/entities')).data as HAEntity[],
    enabled,
  })
}

export function useHAConfig() {
  return useQuery({ queryKey: ['ha-config'], queryFn: async () => (await apiClient.get('/ha/config')).data as HAConfig })
}

export function useSaveHAConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (config: HAConfig) => (await apiClient.put('/ha/config', config)).data as HAConfig,
    onSuccess: (config) => {
      qc.setQueryData(['ha-config'], config)
      void qc.invalidateQueries({ queryKey: ['ha-states'] })
    },
  })
}

/** How a state reads to a person: "On", "12.3 °C", "Open". */
export function stateText(e: HAEntity): string {
  if (e.state === 'unavailable' || e.state === 'unknown') return 'Unavailable'
  if (e.domain === 'binary_sensor') {
    const on = e.state === 'on'
    switch (e.device_class) {
      case 'door': case 'window': case 'opening': case 'garage_door': return on ? 'Open' : 'Closed'
      case 'motion': case 'occupancy': case 'presence': return on ? 'Someone there' : 'Clear'
      case 'moisture': return on ? 'Wet' : 'Dry'
      case 'lock': return on ? 'Unlocked' : 'Locked'
      default: return on ? 'On' : 'Off'
    }
  }
  if (e.domain === 'climate') {
    const now = e.current_temperature != null ? `${e.current_temperature}${e.unit ?? '°'}` : ''
    return [now, e.state === 'off' ? 'off' : e.state].filter(Boolean).join(' · ')
  }
  if (SWITCHABLE.has(e.domain)) return e.state === 'on' ? 'On' : 'Off'
  if (RUNNABLE.has(e.domain)) return ''
  return e.unit ? `${e.state} ${e.unit}` : e.state
}
