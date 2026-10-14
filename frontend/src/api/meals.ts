import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import { dayLabel } from '../lib/meals'
import { offlineWrite } from '../lib/offline'

export type Slot = 'breakfast' | 'lunch' | 'dinner' | 'snack'
export const SLOTS: Slot[] = ['breakfast', 'lunch', 'dinner', 'snack']

export interface RecipeDraft {
  title: string
  description: string | null
  servings: number | null
  prep_minutes: number | null
  cook_minutes: number | null
  ingredients: string[]
  steps: string[]
  tags: string[]
  source_url: string | null
  video_url: string | null
}

export interface Recipe extends RecipeDraft {
  id: string
  catalog_key: string | null
  created_by: string | null
}

export interface CatalogRecipe extends RecipeDraft { key: string; added: boolean }

export interface PlanEntry { id: string; day: string; slot: Slot; recipe_id: string | null; title: string; note: string | null }
export interface PlanWeek { week_start: string; days: string[]; entries: PlanEntry[] }

export interface ShoppingItem {
  id: string
  name: string
  quantity: string | null
  source: 'manual' | 'plan' | 'pantry'
  recipe_id: string | null
  recipe_title: string | null
  week_start: string | null
  checked: boolean
  checked_at: string | null
  checked_by: string | null
  in_pantry: string | null
}

export interface PantryItem {
  id: string
  name: string
  quantity: number | null
  unit: string | null
  low_at: number | null
  expires_on: string | null
  is_low: boolean
  expired: boolean
  expires_soon: boolean
}

export interface EventDraft {
  title: string
  start_dt: string
  end_dt: string
  all_day: boolean
  location: string | null
  description: string | null
}

const get = async <T,>(url: string, params?: object) => (await apiClient.get(url, { params })).data as T

const MEAL_KEYS = [['recipes'], ['meal-catalog'], ['meal-plan'], ['shopping'], ['shopping-history'], ['pantry']]

function useMealsMutation<V, R = unknown>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSettled: () => Promise.all(MEAL_KEYS.map((queryKey) => qc.invalidateQueries({ queryKey }))),
  })
}

// ---- recipes ----

export function useRecipes(params: { q?: string; tag?: string } = {}) {
  return useQuery({ queryKey: ['recipes', params], queryFn: () => get<Recipe[]>('/meals/recipes', params) })
}

export function useSaveRecipe() {
  return useMealsMutation(async ({ id, ...data }: Partial<RecipeDraft> & { id?: string }) =>
    (id ? await apiClient.patch(`/meals/recipes/${id}`, data) : await apiClient.post('/meals/recipes', data)).data as Recipe)
}

export function useDeleteRecipe() {
  return useMealsMutation(async (id: string) => apiClient.delete(`/meals/recipes/${id}`))
}

export function useCatalog() {
  return useQuery({ queryKey: ['meal-catalog'], queryFn: () => get<CatalogRecipe[]>('/meals/catalog') })
}

export function useAddFromCatalog() {
  return useMealsMutation(async (key: string) => (await apiClient.post(`/meals/catalog/${key}`)).data as Recipe)
}

/** Read a recipe from a link or pasted text; nothing is saved. */
export async function importRecipe(source: { url: string } | { text: string }): Promise<RecipeDraft> {
  return (await apiClient.post('/import/recipe', source)).data as RecipeDraft
}

/** Read an event from a link or pasted text; nothing is saved. */
export async function importEvent(source: { url: string } | { text: string }): Promise<EventDraft> {
  return (await apiClient.post('/import/event', source)).data as EventDraft
}

// ---- plan ----

export function usePlan(start: string | undefined) {
  return useQuery({ queryKey: ['meal-plan', start ?? 'this'], queryFn: () => get<PlanWeek>('/meals/plan', start ? { start } : undefined) })
}

/** The slot as this device last saw it, for the offline conflict check (an empty slot is all null). */
function slotAsSeen(qc: QueryClient, day: string, slot: Slot) {
  const entry = qc.getQueriesData<PlanWeek>({ queryKey: ['meal-plan'] })
    .flatMap(([, week]) => week?.entries ?? []).find((e) => e.day === day && e.slot === slot)
  return entry ? { recipe_id: entry.recipe_id, title: entry.title, note: entry.note } : { recipe_id: null, title: null, note: null }
}

/** Show a slot's change at once in every cached week that has that day (null clears it). */
function showSlot(qc: QueryClient, day: string, slot: Slot, entry: PlanEntry | null) {
  qc.setQueriesData<PlanWeek>({ queryKey: ['meal-plan'] }, (week) => {
    if (!week?.days.includes(day)) return week
    const others = week.entries.filter((e) => !(e.day === day && e.slot === slot))
    return { ...week, entries: entry ? [...others, entry] : others }
  })
}

type SlotWrite = { day: string; slot: Slot; recipe_id?: string | null; title?: string | null; note?: string | null }

/** Plan a meal. Works offline (Phase 9): queued with the slot as last seen. */
export function useSetSlot() {
  const qc = useQueryClient()
  return useMutation({
    networkMode: 'always',
    mutationFn: ({ day, slot, ...body }: SlotWrite) => {
      const base = slotAsSeen(qc, day, slot)
      const recipeTitle = body.recipe_id
        ? qc.getQueriesData<Recipe[]>({ queryKey: ['recipes'] }).flatMap(([, rs]) => rs ?? []).find((r) => r.id === body.recipe_id)?.title
        : undefined
      const title = body.title?.trim() || recipeTitle || 'Planned meal'
      showSlot(qc, day, slot, { id: `pending-${day}-${slot}`, day, slot, recipe_id: body.recipe_id ?? null, title, note: body.note ?? null })
      return offlineWrite<PlanEntry>({ method: 'put', url: `/meals/plan/${day}/${slot}`, body, label: `Plan ${slot} on ${dayLabel(day)}: ${title}`,
        refresh: [['meal-plan']], base, local: { recipe_id: body.recipe_id ?? null, title, note: body.note ?? null } })
    },
    onSettled: (res) => { if (!res?.queued) void Promise.all(MEAL_KEYS.map((queryKey) => qc.invalidateQueries({ queryKey }))) },
  })
}

/** Clear a planned meal. Works offline like useSetSlot. */
export function useClearSlot() {
  const qc = useQueryClient()
  return useMutation({
    networkMode: 'always',
    mutationFn: ({ day, slot }: { day: string; slot: Slot }) => {
      const base = slotAsSeen(qc, day, slot)
      showSlot(qc, day, slot, null)
      return offlineWrite<unknown>({ method: 'delete', url: `/meals/plan/${day}/${slot}`, label: `Clear ${slot} on ${dayLabel(day)}`,
        refresh: [['meal-plan']], base, local: { recipe_id: null, title: null, note: null } })
    },
    onSettled: (res) => { if (!res?.queued) void Promise.all(MEAL_KEYS.map((queryKey) => qc.invalidateQueries({ queryKey }))) },
  })
}

// ---- shopping ----

export function useShopping() {
  return useQuery({ queryKey: ['shopping'], queryFn: () => get<ShoppingItem[]>('/meals/shopping') })
}

export function useShoppingHistory(enabled: boolean) {
  return useQuery({ queryKey: ['shopping-history'], queryFn: () => get<ShoppingItem[]>('/meals/shopping/history'), enabled })
}

/** Adding and ticking off work offline: queued, shown at once, synced later (lib/offline). */
export function useAddShopping() {
  const qc = useQueryClient()
  return useMutation({
    networkMode: 'always',
    mutationFn: (body: { name: string; quantity?: string | null }) =>
      offlineWrite<ShoppingItem>({ method: 'post', url: '/meals/shopping', body, label: `Add ${body.name} to the list`, refresh: [['shopping']] }),
    onSuccess: (res, body) => {
      if (!res.queued) return
      qc.setQueryData<ShoppingItem[]>(['shopping'], (items = []) => [...items, {
        id: `pending-${res.write.id}`, name: body.name, quantity: body.quantity ?? null, source: 'manual', recipe_id: null,
        recipe_title: null, week_start: null, checked: false, checked_at: null, checked_by: null, in_pantry: null,
      }])
    },
    onSettled: (res) => { if (!res?.queued) void qc.invalidateQueries({ queryKey: ['shopping'] }) },
  })
}

export function useUpdateShopping() {
  const qc = useQueryClient()
  return useMutation({
    networkMode: 'always',
    mutationFn: ({ id, ...changes }: { id: string; checked?: boolean; name?: string; quantity?: string | null }) => {
      const item = qc.getQueryData<ShoppingItem[]>(['shopping'])?.find((i) => i.id === id)
      const base = item ? { name: item.name, quantity: item.quantity, checked: item.checked } : undefined
      const label = changes.checked === undefined ? `Change ${item?.name ?? 'an item'}` : `${changes.checked ? 'Tick off' : 'Untick'} ${item?.name ?? 'an item'}`
      // Snapshot first, then show the change: the snapshot must be what was seen *before* it.
      qc.setQueryData<ShoppingItem[]>(['shopping'], (items) => items?.map((i) => (i.id === id ? { ...i, ...changes } : i)))
      return offlineWrite<ShoppingItem>({ method: 'patch', url: `/meals/shopping/${id}`, body: changes, label,
        refresh: [['shopping']], base, local: changes })
    },
    onSettled: (res) => { if (!res?.queued) void qc.invalidateQueries({ queryKey: ['shopping'] }) },
  })
}

export function useDeleteShopping() {
  return useMealsMutation(async (id: string) => apiClient.delete(`/meals/shopping/${id}`))
}

export function useShoppingFromPlan() {
  return useMealsMutation(async (start: string | undefined) =>
    (await apiClient.post('/meals/shopping/from-plan', undefined, start ? { params: { start } } : undefined)).data as
      { added: number; removed: number; week_start: string })
}

export function useClearChecked() {
  return useMealsMutation<void, { archived: number }>(async () => (await apiClient.post('/meals/shopping/clear-checked')).data)
}

// ---- pantry ----

export function usePantry() {
  return useQuery({ queryKey: ['pantry'], queryFn: () => get<PantryItem[]>('/meals/pantry') })
}

export type PantryInput = Partial<Pick<PantryItem, 'name' | 'quantity' | 'unit' | 'low_at' | 'expires_on'>>

export function useSavePantry() {
  return useMealsMutation(async ({ id, ...data }: PantryInput & { id?: string }) =>
    (id ? await apiClient.patch(`/meals/pantry/${id}`, data) : await apiClient.post('/meals/pantry', data)).data as PantryItem)
}

export function useDeletePantry() {
  return useMealsMutation(async (id: string) => apiClient.delete(`/meals/pantry/${id}`))
}

export function useRestock() {
  return useMealsMutation<void, { added: number }>(async () => (await apiClient.post('/meals/pantry/restock')).data)
}
