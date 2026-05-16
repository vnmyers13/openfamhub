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
      return res.data as Array<{ id: string; display_name: string; color_hex: string; provider: string }>
    },
  })
}
