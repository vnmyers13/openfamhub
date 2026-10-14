import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

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

export function useSetSlot() {
  return useMealsMutation(async ({ day, slot, ...body }: { day: string; slot: Slot; recipe_id?: string | null; title?: string | null; note?: string | null }) =>
    (await apiClient.put(`/meals/plan/${day}/${slot}`, body)).data as PlanEntry)
}

export function useClearSlot() {
  return useMealsMutation(async ({ day, slot }: { day: string; slot: Slot }) => apiClient.delete(`/meals/plan/${day}/${slot}`))
}

// ---- shopping ----

export function useShopping() {
  return useQuery({ queryKey: ['shopping'], queryFn: () => get<ShoppingItem[]>('/meals/shopping') })
}

export function useShoppingHistory(enabled: boolean) {
  return useQuery({ queryKey: ['shopping-history'], queryFn: () => get<ShoppingItem[]>('/meals/shopping/history'), enabled })
}

export function useAddShopping() {
  return useMealsMutation(async (body: { name: string; quantity?: string | null }) =>
    (await apiClient.post('/meals/shopping', body)).data as ShoppingItem)
}

export function useUpdateShopping() {
  return useMealsMutation(async ({ id, ...body }: { id: string; checked?: boolean; name?: string; quantity?: string | null }) =>
    (await apiClient.patch(`/meals/shopping/${id}`, body)).data as ShoppingItem)
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
