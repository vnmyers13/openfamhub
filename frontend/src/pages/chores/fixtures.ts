import { useAuthStore, type User } from '../../stores/auth'
import { mockApi } from '../../test/api'

export const MEMBERS = [
  { id: 'mom', display_name: 'Mom', role: 'admin', color_hex: '#4F46E5', avatar_value: null },
  { id: 'kid', display_name: 'Kid', role: 'member', color_hex: '#059669', avatar_value: null },
  { id: 'gm', display_name: 'Grandma', role: 'viewer', color_hex: '#DC2626', avatar_value: null },
]

export const inst = (id: string, title: string, over: object = {}) => ({
  id, template_id: `t-${id}`, title, points: 5, due_date: '2026-10-12', status: 'pending', assigned_to: null,
  claimed_by: null, completed_by: null, completed_at: null, routine_id: null, ...over,
})

export function signIn(id: string, role: string) {
  useAuthStore.getState().setUser({ id, display_name: id, role, family_id: 'f' } as User)
}

/** The Today tab's API, plus whatever a test adds. */
export function choresApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /users/': MEMBERS,
    'GET /chores/instances': (params: unknown) => {
      const scope = (params as { scope: string }).scope
      if (scope === 'mine') {
        return [inst('a', 'Feed the cat', { assigned_to: 'kid' }),
          inst('d', 'Dishes', { status: 'completed', completed_by: 'kid', assigned_to: 'kid' })]
      }
      if (scope === 'available') return [inst('b', 'Take out bins')]
      return [inst('a', 'Feed the cat', { assigned_to: 'kid' }), inst('b', 'Take out bins')]
    },
    'GET /chores/stats': { user_id: 'kid', completed_total: 3, completed_this_week: 2, points_balance: 15, streak_days: 4 },
    'POST /chores/instances/a/complete': inst('a', 'Feed the cat', { status: 'completed' }),
    'POST /chores/instances/b/claim': inst('b', 'Take out bins', { status: 'claimed', claimed_by: 'kid' }),
    'POST /chores/instances/d/undo': inst('d', 'Dishes'),
    ...extra,
  })
}
