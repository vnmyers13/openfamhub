import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { CalendarEvent } from './calendar'

export interface WallMember {
  id: string
  display_name: string
  color_hex: string
}

export interface WallDevice {
  id: string
  name: string
  last_seen_at: string | null
  created_at: string | null
}

// ---- display side (authenticated by the wall_token cookie) ----

export async function pairWall(token: string) {
  await apiClient.post('/wall/pair', { token })
}

export async function getWallSession() {
  const res = await apiClient.get('/wall/session')
  return res.data as { device: string; family_name: string | null }
}

export function useWallEvents(start: Date, end: Date) {
  return useQuery({
    queryKey: ['wall-events', start.toISOString(), end.toISOString()],
    queryFn: async () => {
      const res = await apiClient.get('/wall/events', {
        params: { start: start.toISOString(), end: end.toISOString() },
      })
      return res.data as CalendarEvent[]
    },
    refetchInterval: 15 * 60 * 1000, // backstop in case the WebSocket drops
  })
}

export function useWallMembers() {
  return useQuery({
    queryKey: ['wall-members'],
    queryFn: async () => (await apiClient.get('/wall/members')).data as WallMember[],
  })
}

// ---- admin side ----

export function useWallDevices() {
  return useQuery({
    queryKey: ['wall-devices'],
    queryFn: async () => (await apiClient.get('/wall/devices')).data as WallDevice[],
  })
}

export function useCreateWallDevice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (name: string) =>
      (await apiClient.post('/wall/devices', { name })).data as WallDevice & { token: string },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wall-devices'] }),
  })
}

export function useRevokeWallDevice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/wall/devices/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wall-devices'] }),
  })
}
