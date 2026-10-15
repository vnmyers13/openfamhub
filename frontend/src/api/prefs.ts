import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { WidgetKey } from '../lib/dashboard'

export interface DashboardWidget { key: WidgetKey; size: 'normal' | 'wide' }
export interface DashboardPage { name: string; widgets: DashboardWidget[] }
export type Wallpaper = 'none' | 'dusk' | 'ocean' | 'forest' | 'sunrise' | 'photo'

/** Which reminders a person gets on their devices (Phase 11; backend jobs/reminders.py). */
export interface NotificationPrefs {
  events: 'off' | 'mine' | 'all'
  event_minutes: 5 | 10 | 15 | 30 | 60
  daily: boolean
  daily_time: string  // HH:MM, family timezone
  rewards: boolean  // admins
  birthdays: boolean  // the day before, at daily_time
  pantry: boolean  // members and admins: use-by dates, at daily_time
  allowance: boolean  // their weekly allowance was paid
  ntfy_topic: string | null  // their own topic on the server's ntfy
  email_to: string | null  // where to email them
  water: boolean  // wellness: devices and ntfy only, never email
  water_every: 60 | 90 | 120 | 180  // minutes
  water_from: string  // HH:MM
  water_until: string  // HH:MM, after water_from
  mindful: boolean
  mindful_time: string  // HH:MM
}

export const DEFAULT_NOTIFICATIONS: NotificationPrefs = { events: 'off', event_minutes: 15, daily: true, daily_time: '07:00', rewards: true,
  birthdays: true, pantry: true, allowance: true, ntfy_topic: null, email_to: null,
  water: false, water_every: 120, water_from: '09:00', water_until: '20:00', mindful: false, mindful_time: '15:00',
}

/** Channels besides Web Push that the server has set up (NTFY_URL, SMTP_* on the server). */
export interface NotifyChannels { ntfy: string | null; email: boolean }

export function useNotifyChannels() {
  return useQuery({
    queryKey: ['notify-channels'],
    queryFn: async () => (await apiClient.get('/push/channels')).data as NotifyChannels,
    staleTime: 10 * 60_000,
  })
}

/** One person's layout choices, saved on the server so they follow them to every device. */
export interface Preferences {
  nav: 'side' | 'top'
  calendar_scope: 'family' | 'mine'
  wallpaper: Wallpaper
  wallpaper_media_id: string | null
  pages: DashboardPage[]
  notifications: NotificationPrefs
}

export const DEFAULT_PREFS: Preferences = {
  nav: 'side', calendar_scope: 'family', wallpaper: 'none', wallpaper_media_id: null, pages: [], notifications: DEFAULT_NOTIFICATIONS,
}

export function usePreferences() {
  return useQuery({
    queryKey: ['preferences'],
    queryFn: async () => ({ ...DEFAULT_PREFS, ...((await apiClient.get('/users/me/preferences')).data as Partial<Preferences>) }),
    staleTime: Infinity,
  })
}

/** Save the whole set; the screen updates at once and settles to what the server kept. */
export function useSavePreferences() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (prefs: Preferences) => (await apiClient.put('/users/me/preferences', prefs)).data as Preferences,
    onMutate: (prefs) => {
      const before = qc.getQueryData<Preferences>(['preferences'])
      qc.setQueryData(['preferences'], prefs)
      return { before }
    },
    onError: (_err, _prefs, ctx) => { if (ctx?.before) qc.setQueryData(['preferences'], ctx.before) },
    onSuccess: (saved) => qc.setQueryData(['preferences'], { ...DEFAULT_PREFS, ...saved }),
  })
}
