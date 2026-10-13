import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { apiClient } from './client'
import type { CalendarEvent } from './calendar'
import type { SleepSchedule } from '../lib/sleep'

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

/**
 * Call `listener` when the server rejects this display's device cookie (401
 * on a display endpoint), e.g. after an admin revokes it. Pairing requests are
 * excluded: a bad pairing link is handled by the pairing flow itself.
 * Returns an unsubscribe function.
 */
export function onWallUnauthorized(listener: () => void): () => void {
  const id = apiClient.interceptors.response.use(undefined, (err: unknown) => {
    if (isAxiosError(err) && err.response?.status === 401) {
      const path = (err.config?.url ?? '').replace(/^\/+/, '')
      if (path.startsWith('wall/') && !path.startsWith('wall/pair') && !path.startsWith('wall/devices')) {
        listener()
      }
    }
    return Promise.reject(err)
  })
  return () => apiClient.interceptors.response.eject(id)
}

export async function pairWall(token: string) {
  await apiClient.post('/wall/pair', { token })
}

export interface WallSession {
  device: string
  family_name: string | null
  idle_timeout_seconds: number
  timezone: string
  sleep: SleepSchedule
}

export async function getWallSession() {
  const res = await apiClient.get('/wall/session')
  return res.data as WallSession
}

export interface WallMediaItem {
  id: string
  kind: 'photo' | 'video'
  width: number | null
  height: number | null
  duration_s: number | null
  wall_url: string
  thumb_url: string
}

/** The slideshow's media (ready items only), refreshed on media_updated pushes. */
export function useWallMedia() {
  return useQuery({
    queryKey: ['wall-media'],
    queryFn: async () => (await apiClient.get('/wall/media')).data as WallMediaItem[],
    refetchInterval: 15 * 60 * 1000,
  })
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
