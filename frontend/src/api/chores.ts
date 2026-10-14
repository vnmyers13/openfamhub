import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import { offlineWrite } from '../lib/offline'
import type { Repeat } from '../lib/repeat'

export interface Member {
  id: string
  display_name: string
  role: string
  color_hex: string
  avatar_value: string | null
}

export interface ChoreTemplate {
  id: string
  title: string
  description: string | null
  points: number
  assignment: 'assigned' | 'claimable'
  assigned_to: string | null
  repeat: Repeat | null
  start_date: string
  is_active: boolean
}

export interface ChoreInstance {
  id: string
  template_id: string
  title: string
  points: number
  due_date: string
  status: 'pending' | 'claimed' | 'completed' | 'missed'
  assigned_to: string | null
  claimed_by: string | null
  completed_by: string | null
  completed_at: string | null
  routine_id: string | null
}

export interface ChoreStats {
  user_id: string
  completed_total: number
  completed_this_week: number
  points_balance: number
  streak_days: number
}

export interface Todo {
  id: string
  title: string
  notes: string | null
  assigned_to: string | null
  due_date: string | null
  done: boolean
  completed_by: string | null
  created_by: string | null
}

export interface RoutineStep { id?: string; title: string; minutes: number; points: number }
export interface Routine {
  id: string
  name: string
  assigned_to: string | null
  start_time: string | null
  repeat: Repeat | null
  start_date: string
  steps: (RoutineStep & { id: string })[]
}
export interface RoutineRun {
  id: string
  name: string
  assigned_to: string | null
  assigned_name: string | null
  assigned_color: string | null
  start_time: string | null
  steps: { instance_id: string; template_id: string; title: string; minutes: number; points: number; status: ChoreInstance['status'] }[]
}

const get = async <T,>(url: string, params?: object) => (await apiClient.get(url, { params })).data as T

/** Everything that depends on chore state; invalidated after any change. */
const CHORE_KEYS = [['chore-instances'], ['chore-templates'], ['chore-stats'], ['chore-points'], ['chore-log'],
  ['chore-by-user'], ['routines'], ['routines-today']]

function useInvalidateChores() {
  const qc = useQueryClient()
  return () => Promise.all(CHORE_KEYS.map((queryKey) => qc.invalidateQueries({ queryKey })))
}

export function useFamilyMembers() {
  return useQuery({ queryKey: ['users'], queryFn: () => get<Member[]>('/users/') })
}

export function useChoreInstances(scope: 'mine' | 'available' | 'family') {
  return useQuery({ queryKey: ['chore-instances', scope], queryFn: () => get<ChoreInstance[]>('/chores/instances', { scope }) })
}

const ACTION_LABEL = { claim: 'Claim', unclaim: 'Give back', complete: 'Finish', undo: 'Undo' } as const
const ACTION_STATUS = { claim: 'claimed', unclaim: 'pending', complete: 'completed', undo: 'pending' } as const

/** Chore taps work offline: queued, shown at once, synced later (lib/offline). */
export function useChoreAction() {
  const qc = useQueryClient()
  const invalidate = useInvalidateChores()
  return useMutation({
    networkMode: 'always',
    mutationFn: ({ id, action, title }: { id: string; action: 'claim' | 'unclaim' | 'complete' | 'undo'; title?: string }) =>
      offlineWrite<ChoreInstance>({ method: 'post', url: `/chores/instances/${id}/${action}`,
        label: `${ACTION_LABEL[action]}: ${title ?? 'a chore'}`, refresh: CHORE_KEYS }),
    onMutate: ({ id, action }) => {
      qc.setQueriesData<ChoreInstance[]>({ queryKey: ['chore-instances'] },
        (list) => list?.map((c) => (c.id === id ? { ...c, status: ACTION_STATUS[action] } : c)))
    },
    onSettled: (res) => (res?.queued ? undefined : invalidate()),
  })
}

export function useChoreTemplates() {
  return useQuery({ queryKey: ['chore-templates'], queryFn: () => get<ChoreTemplate[]>('/chores/templates') })
}

export type ChoreInput = Partial<Pick<ChoreTemplate, 'title' | 'points' | 'assignment' | 'assigned_to' | 'repeat' | 'start_date'>>

export function useSaveChore() {
  const invalidate = useInvalidateChores()
  return useMutation({
    mutationFn: async ({ id, ...data }: ChoreInput & { id?: string }) =>
      (id ? await apiClient.patch(`/chores/templates/${id}`, data) : await apiClient.post('/chores/templates', data)).data as ChoreTemplate,
    onSettled: invalidate,
  })
}

export function useRetireChore() {
  const invalidate = useInvalidateChores()
  return useMutation({ mutationFn: (id: string) => apiClient.delete(`/chores/templates/${id}`), onSettled: invalidate })
}

export function useChoreByUser() {
  return useQuery({
    queryKey: ['chore-by-user'],
    queryFn: () => get<{ user_id: string | null; display_name: string; pending: number; completed: number; missed: number }[]>('/chores/by-user'),
  })
}

export function useChoreStats() {
  return useQuery({ queryKey: ['chore-stats'], queryFn: () => get<ChoreStats>('/chores/stats') })
}

export function useFamilyPoints() {
  return useQuery({
    queryKey: ['chore-points'],
    queryFn: () => get<{ user_id: string; display_name: string; points: number }[]>('/chores/points'),
  })
}

export function useChoreLog() {
  return useQuery({
    queryKey: ['chore-log'],
    queryFn: () => get<{ id: string; title: string; completed_by: string; credited_to: string | null; points: number;
      completed_at: string; undone_at: string | null }[]>('/chores/log'),
  })
}

// ---- to-dos ----

export function useTodos(includeDone: boolean) {
  return useQuery({ queryKey: ['todos', includeDone], queryFn: () => get<Todo[]>('/todos', { include_done: includeDone }) })
}

/** Adding and ticking off to-dos work offline: queued, shown at once, synced later (lib/offline). */
export function useSaveTodo() {
  const qc = useQueryClient()
  return useMutation({
    networkMode: 'always',
    mutationFn: ({ id, ...data }: Partial<Todo> & { id?: string }) => {
      if (!id) return offlineWrite<Todo>({ method: 'post', url: '/todos', body: data, label: `Add to-do: ${data.title ?? ''}`, refresh: [['todos']] })
      const todo = qc.getQueriesData<Todo[]>({ queryKey: ['todos'] }).flatMap(([, list]) => list ?? []).find((t) => t.id === id)
      const base = todo ? { title: todo.title, notes: todo.notes, assigned_to: todo.assigned_to, due_date: todo.due_date, done: todo.done } : undefined
      const label = data.done === undefined ? `Change to-do: ${todo?.title ?? ''}` : `${data.done ? 'Tick off' : 'Untick'} to-do: ${todo?.title ?? ''}`
      // Snapshot first, then show the change: the snapshot must be what was seen *before* it.
      qc.setQueriesData<Todo[]>({ queryKey: ['todos'] }, (list) => list?.map((t) => (t.id === id ? { ...t, ...data } : t)))
      return offlineWrite<Todo>({ method: 'patch', url: `/todos/${id}`, body: data, label, refresh: [['todos']], base, local: data })
    },
    onSuccess: (res, vars) => {
      if (!res.queued || vars.id) return
      qc.setQueriesData<Todo[]>({ queryKey: ['todos'] }, (list) => list && [...list, {
        id: `pending-${res.write.id}`, title: vars.title ?? '', notes: vars.notes ?? null, assigned_to: vars.assigned_to ?? null,
        due_date: vars.due_date ?? null, done: false, completed_by: null, created_by: null,
      }])
    },
    onSettled: (res) => { if (!res?.queued) void qc.invalidateQueries({ queryKey: ['todos'] }) },
  })
}

export function useDeleteTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/todos/${id}`),
    onSettled: () => qc.invalidateQueries({ queryKey: ['todos'] }),
  })
}

// ---- routines ----

export function useRoutines() {
  return useQuery({ queryKey: ['routines'], queryFn: () => get<Routine[]>('/routines') })
}

export function useTodayRoutines() {
  return useQuery({ queryKey: ['routines-today'], queryFn: () => get<RoutineRun[]>('/routines/today') })
}

export type RoutineInput = Partial<Omit<Routine, 'id' | 'steps'>> & { steps?: RoutineStep[] }

export function useSaveRoutine() {
  const invalidate = useInvalidateChores()
  return useMutation({
    mutationFn: async ({ id, ...data }: RoutineInput & { id?: string }) =>
      (id ? await apiClient.patch(`/routines/${id}`, data) : await apiClient.post('/routines', data)).data as Routine,
    onSettled: invalidate,
  })
}

export function useRetireRoutine() {
  const invalidate = useInvalidateChores()
  return useMutation({ mutationFn: (id: string) => apiClient.delete(`/routines/${id}`), onSettled: invalidate })
}
