import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

interface CalendarEvent {
  id: string
  source_id: string
  title: string
  start_dt: string
  end_dt: string
  all_day: boolean
  location: string | null
  description: string | null
  created_by: string | null
  source_color_hex: string
  created_at: string | null
  updated_at: string | null
}

interface CreateEventData {
  title: string
  start_dt: string
  end_dt: string
  all_day?: boolean
  location?: string
  description?: string
}

export interface CalendarSource {
  id: string
  family_id: string
  provider: string
  display_name: string
  color_hex: string
  ics_url: string | null
  sync_interval_hours: number
  last_synced_at: string | null
  sync_error: string | null
  enabled: boolean
  created_at: string | null
  updated_at: string | null
}

export interface SyncLogEntry {
  id: string
  source_id: string
  synced_at: string
  events_upserted: number
  events_deleted: number
  duration_ms: number
  error: string | null
}

export function useCalendarEvents(start: Date, end: Date) {
  return useQuery({
    queryKey: ['calendar-events', start.toISOString(), end.toISOString()],
    queryFn: async () => {
      const res = await apiClient.get('/calendar/events', {
        params: { start: start.toISOString(), end: end.toISOString() },
      })
      return res.data as CalendarEvent[]
    },
  })
}

export function useCreateEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: CreateEventData) => {
      const res = await apiClient.post('/calendar/events', data)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-events'] })
    },
  })
}

export function usePatchEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...data }: { id: string } & Partial<CreateEventData>) => {
      const res = await apiClient.patch(`/calendar/events/${id}`, data)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-events'] })
    },
  })
}

export function useDeleteEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/calendar/events/${id}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-events'] })
    },
  })
}

export function useCalendarSources() {
  return useQuery({
    queryKey: ['calendar-sources'],
    queryFn: async () => {
      const res = await apiClient.get('/calendar/sources')
      return res.data as CalendarSource[]
    },
  })
}

export function useAddIcalSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { ics_url: string; display_name: string; color_hex: string; sync_interval_hours: number }) => {
      const res = await apiClient.post('/integrations/ical', data)
      return res.data as CalendarSource
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-sources'] })
    },
  })
}

export function useSyncSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const res = await apiClient.post(`/calendar/sources/${sourceId}/sync`)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-sources'] })
    },
  })
}

export function useDeleteCalendarSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (sourceId: string) => {
      await apiClient.delete(`/calendar/sources/${sourceId}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar-sources'] })
    },
  })
}

export function useSourceLogs(sourceId: string | null) {
  return useQuery({
    queryKey: ['source-logs', sourceId],
    queryFn: async () => {
      const res = await apiClient.get(`/calendar/sources/${sourceId}/log`)
      return res.data as SyncLogEntry[]
    },
    enabled: !!sourceId,
  })
}
