import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import type { WorldClock } from './family'
import { apiClient } from './client'
import type { CalendarEvent } from './calendar'
import type { SleepSchedule } from '../lib/sleep'
import type { ChoreInstance, RoutineRun } from './chores'
import type { ProgressRow } from './rewards'
import type { Announcement, UpcomingBirthday, Weather } from './home'

export const WALL_DASHBOARD_WIDGETS = [
  { key: 'events', label: "Today's events" },
  { key: 'chores', label: 'Chores' },
  { key: 'routines', label: 'Routines' },
  { key: 'meals', label: "Today's meals" },
  { key: 'weather', label: 'Weather' },
  { key: 'announcements', label: 'Announcements' },
  { key: 'progress', label: 'Family progress' },
  { key: 'birthdays', label: 'Birthdays' },
] as const

export type WallDashboardWidgetKey = (typeof WALL_DASHBOARD_WIDGETS)[number]['key']
export interface WallDashboardWidget { key: WallDashboardWidgetKey; size: 'normal' | 'wide' }
export interface WallDashboardPage { name: string; duration_seconds: number; widgets: WallDashboardWidget[] }
export interface WallDashboardConfig { pages: WallDashboardPage[] }

export const DEFAULT_WALL_DASHBOARD: WallDashboardConfig = {
  pages: [
    { name: 'Today', duration_seconds: 30, widgets: [{ key: 'events', size: 'wide' }, { key: 'weather', size: 'normal' }, { key: 'meals', size: 'normal' }] },
    { name: 'Family', duration_seconds: 30, widgets: [{ key: 'routines', size: 'wide' }, { key: 'progress', size: 'wide' }] },
    { name: 'Notes', duration_seconds: 30, widgets: [{ key: 'announcements', size: 'wide' }, { key: 'birthdays', size: 'normal' }] },
  ],
}

export const wallDashboardWidgetLabel = (key: WallDashboardWidgetKey) => WALL_DASHBOARD_WIDGETS.find((w) => w.key === key)?.label ?? key

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
  clocks?: WorldClock[]
  dashboard: WallDashboardConfig
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

export function useWallChores() {
  return useQuery({
    queryKey: ['wall-chores'],
    queryFn: async () => (await apiClient.get('/wall/chores')).data as ChoreInstance[],
    refetchInterval: 5 * 60 * 1000,
  })
}

export interface WallMeal { day: string; slot: string; title: string; recipe_id: string | null; note: string | null }
export interface WallMeals { week_start: string; days: string[]; entries: WallMeal[] }

export function useWallMeals() {
  return useQuery({
    queryKey: ['wall-meals'],
    queryFn: async () => (await apiClient.get('/wall/meals')).data as WallMeals,
    refetchInterval: 15 * 60 * 1000,
  })
}

export function useWallAnnouncements() {
  return useQuery({
    queryKey: ['wall-announcements'],
    queryFn: async () => (await apiClient.get('/wall/announcements')).data as Announcement[],
    refetchInterval: 5 * 60 * 1000,
  })
}

export function useWallWeather() {
  return useQuery({
    queryKey: ['wall-weather'],
    queryFn: async () => (await apiClient.get('/wall/weather')).data as Weather,
    refetchInterval: 15 * 60 * 1000,
  })
}

/** Birthdays in the next two weeks, for the wall's birthday card. */
export function useWallBirthdays() {
  return useQuery({
    queryKey: ['wall-birthdays'],
    queryFn: async () => (await apiClient.get('/wall/birthdays')).data as UpcomingBirthday[],
    refetchInterval: 60 * 60 * 1000,
  })
}

/** Family points, streaks and badges, refreshed on chores_updated / rewards_updated pushes. */
export function useWallProgress() {
  return useQuery({
    queryKey: ['wall-progress'],
    queryFn: async () => (await apiClient.get('/wall/progress')).data as ProgressRow[],
    refetchInterval: 15 * 60 * 1000,
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

export function useFamilyWallDashboardConfig() {
  return useQuery({
    queryKey: ['family-wall-dashboard'],
    queryFn: async () => ({ ...DEFAULT_WALL_DASHBOARD, ...((await apiClient.get('/family/wall-dashboard')).data as WallDashboardConfig) }),
  })
}

export function useSaveFamilyWallDashboardConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (config: WallDashboardConfig) => (await apiClient.put('/family/wall-dashboard', config)).data as WallDashboardConfig,
    onMutate: (config) => {
      const before = qc.getQueryData<WallDashboardConfig>(['family-wall-dashboard'])
      qc.setQueryData(['family-wall-dashboard'], config)
      return { before }
    },
    onError: (_err, _config, ctx) => { if (ctx?.before) qc.setQueryData(['family-wall-dashboard'], ctx.before) },
    onSuccess: (saved) => qc.setQueryData(['family-wall-dashboard'], saved),
  })
}

/** Today's routines for the wall's countdown (refreshed on chores_updated pushes). */
export function useWallRoutines() {
  return useQuery({
    queryKey: ['wall-routines'],
    queryFn: async () => (await apiClient.get('/wall/routines')).data as RoutineRun[],
    refetchInterval: 5 * 60 * 1000,
  })
}
