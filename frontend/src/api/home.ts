import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { CalendarEvent } from './calendar'

export interface Announcement { id: string; body: string; pinned: boolean; author_id: string | null; created_at: string }

export interface UpcomingBirthday {
  user_id: string
  display_name: string
  color_hex: string
  avatar_value: string | null
  date: string
  turns: number
  days_away: number
}

export interface MealSlot { day: string; slot: string; title: string; recipe_id: string | null }

export interface DashboardSummary {
  today: string
  events_today: CalendarEvent[]
  chores: { mine_open: number; mine_done: number; family_open: number; family_done: number }
  points_balance: number
  allowance_cents: number
  meals_today: MealSlot[]
  meals_week: MealSlot[]
  birthdays: UpcomingBirthday[]
  announcements: Announcement[]
}

export interface WeatherDay { date: string; emoji: string; label: string; high: number | null; low: number | null; precip_chance: number | null }
export interface Weather {
  configured: boolean
  place?: string | null
  units?: 'fahrenheit' | 'celsius' | null
  temperature?: number | null
  emoji?: string | null
  label?: string | null
  wind?: number | null
  days?: WeatherDay[]
  error?: string | null
}
export interface Place { name: string; latitude: number; longitude: number }
export interface WeatherLocation extends Place { units: 'fahrenheit' | 'celsius' }

export type BookStatus = 'want_to_read' | 'reading' | 'finished'
export interface Book {
  id: string
  title: string
  author: string | null
  notes: string | null
  status: BookStatus
  owner_id: string | null
  reader_id: string | null
  finished_at: string | null
  added_by: string | null
  points_awarded: boolean
}

const get = async <T,>(url: string, params?: object) => (await apiClient.get(url, { params })).data as T

function useHomeMutation<V, R = unknown>(fn: (v: V) => Promise<R>, keys: string[][]) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSettled: () => Promise.all(keys.map((queryKey) => qc.invalidateQueries({ queryKey }))) })
}

export function useDashboardSummary(scope: 'family' | 'mine' = 'family') {
  return useQuery({
    queryKey: ['dashboard', scope],
    queryFn: () => get<DashboardSummary>('/dashboard/summary', scope === 'mine' ? { scope } : undefined),
    refetchInterval: 5 * 60_000,
  })
}

export function useWeather() {
  return useQuery({ queryKey: ['weather'], queryFn: () => get<Weather>('/weather'), refetchInterval: 15 * 60_000 })
}

// ---- announcements ----

const ANNOUNCE_KEYS = [['announcements'], ['dashboard']]

export function useAnnouncements() {
  return useQuery({ queryKey: ['announcements'], queryFn: () => get<Announcement[]>('/announcements') })
}

export function usePostAnnouncement() {
  return useHomeMutation(async (body: { body: string; pinned?: boolean }) =>
    (await apiClient.post('/announcements', body)).data as Announcement, ANNOUNCE_KEYS)
}

export function useUpdateAnnouncement() {
  return useHomeMutation(async ({ id, ...body }: { id: string; body?: string; pinned?: boolean }) =>
    (await apiClient.patch(`/announcements/${id}`, body)).data as Announcement, ANNOUNCE_KEYS)
}

export function useDeleteAnnouncement() {
  return useHomeMutation(async (id: string) => apiClient.delete(`/announcements/${id}`), ANNOUNCE_KEYS)
}

// ---- weather settings (admin) ----

export function useWeatherLocation() {
  return useQuery({ queryKey: ['weather-location'], queryFn: () => get<WeatherLocation | null>('/weather/location') })
}

export async function searchPlaces(q: string): Promise<Place[]> {
  return get<Place[]>('/weather/places', { q })
}

export function useSetWeatherLocation() {
  return useHomeMutation(async (loc: WeatherLocation | null) =>
    loc ? (await apiClient.put('/weather/location', loc)).data : apiClient.delete('/weather/location'),
  [['weather'], ['weather-location']])
}

// ---- books ----

const BOOK_KEYS = [['books'], ['progress'], ['chore-stats'], ['dashboard']]

export function useBooks(shelf: 'mine' | 'family' | 'everyone', userId?: string) {
  return useQuery({
    queryKey: ['books', shelf, userId ?? ''],
    queryFn: () => get<Book[]>('/books', { shelf, ...(userId ? { user_id: userId } : {}) }),
  })
}

export function useAddBook() {
  return useHomeMutation(async (body: { title: string; author?: string | null; shelf: 'mine' | 'family'; status?: BookStatus }) =>
    (await apiClient.post('/books', body)).data as Book, BOOK_KEYS)
}

export function useUpdateBook() {
  return useHomeMutation(async ({ id, ...body }: { id: string; status?: BookStatus; title?: string; author?: string | null; notes?: string | null }) =>
    (await apiClient.patch(`/books/${id}`, body)).data as Book, BOOK_KEYS)
}

export function useDeleteBook() {
  return useHomeMutation(async (id: string) => apiClient.delete(`/books/${id}`), BOOK_KEYS)
}
