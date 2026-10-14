import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { WidgetKey } from '../lib/dashboard'

export interface DashboardWidget { key: WidgetKey; size: 'normal' | 'wide' }
export interface DashboardPage { name: string; widgets: DashboardWidget[] }
export type Wallpaper = 'none' | 'dusk' | 'ocean' | 'forest' | 'sunrise' | 'photo'

/** One person's layout choices, saved on the server so they follow them to every device. */
export interface Preferences {
  nav: 'side' | 'top'
  calendar_scope: 'family' | 'mine'
  wallpaper: Wallpaper
  wallpaper_media_id: string | null
  pages: DashboardPage[]
}

export const DEFAULT_PREFS: Preferences = { nav: 'side', calendar_scope: 'family', wallpaper: 'none', wallpaper_media_id: null, pages: [] }

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
