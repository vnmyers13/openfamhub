import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from './client'
import { allWrites } from '../lib/idb'
import { replay, useOffline } from '../lib/offline'
import { mockApi } from '../test/api'
import { useClearSlot, useSetSlot, type PlanWeek } from './meals'

const WEEK: PlanWeek = {
  week_start: '2026-10-19',
  days: ['2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23', '2026-10-24', '2026-10-25'],
  entries: [{ id: 'e1', day: '2026-10-20', slot: 'dinner', recipe_id: null, title: 'Tacos', note: null }],
}

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  qc.setQueryData(['meal-plan', 'this'], WEEK)
  qc.setQueryData(['recipes', {}], [{ id: 'r1', title: 'Pancakes' }])
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  return { qc, wrapper }
}

describe('meal plan offline', () => {
  beforeEach(() => {
    globalThis.indexedDB = new IDBFactory()
    useOffline.setState({ online: false, pending: [], syncing: false, signInNeeded: false })
  })

  it('a meal planned offline shows at once and queues with the slot as last seen', async () => {
    mockApi({})
    const { qc, wrapper } = setup()
    const { result } = renderHook(() => useSetSlot(), { wrapper })
    await act(() => result.current.mutateAsync({ day: '2026-10-21', slot: 'lunch', recipe_id: 'r1', title: null }))
    const week = qc.getQueryData<PlanWeek>(['meal-plan', 'this'])!
    expect(week.entries.find((e) => e.day === '2026-10-21')).toMatchObject({ slot: 'lunch', recipe_id: 'r1', title: 'Pancakes' })
    const [w] = await allWrites()
    expect(w).toMatchObject({ method: 'put', url: '/meals/plan/2026-10-21/lunch', label: 'Plan lunch on Wed 21: Pancakes',
      body: { recipe_id: 'r1', title: null, base: { recipe_id: null, title: null, note: null } } })
  })

  it('a meal cleared offline disappears at once; the queued clear carries what was there', async () => {
    mockApi({})
    const { qc, wrapper } = setup()
    const { result } = renderHook(() => useClearSlot(), { wrapper })
    await act(() => result.current.mutateAsync({ day: '2026-10-20', slot: 'dinner' }))
    expect(qc.getQueryData<PlanWeek>(['meal-plan', 'this'])!.entries).toEqual([])
    const [w] = await allWrites()
    expect(w).toMatchObject({ method: 'delete', url: '/meals/plan/2026-10-20/dinner',
      body: { base: { recipe_id: null, title: 'Tacos', note: null } } })
  })

  it('online, the write goes straight out without the check', async () => {
    useOffline.setState({ online: true })
    const calls = mockApi({ 'PUT /meals/plan/2026-10-20/dinner': { id: 'e1' } })
    const { wrapper } = setup()
    const { result } = renderHook(() => useSetSlot(), { wrapper })
    await act(() => result.current.mutateAsync({ day: '2026-10-20', slot: 'dinner', recipe_id: null, title: 'Curry' }))
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ recipe_id: null, title: 'Curry' })
    expect(await allWrites()).toEqual([])
  })

  it('replaying a queued clear sends its check in the request body', async () => {
    mockApi({})
    const { wrapper } = setup()
    const { result } = renderHook(() => useClearSlot(), { wrapper })
    await act(() => result.current.mutateAsync({ day: '2026-10-20', slot: 'dinner' }))
    const del = vi.spyOn(apiClient, 'delete').mockResolvedValue({ data: { message: 'Cleared' } } as never)
    useOffline.setState({ online: true })
    await replay()
    expect(del).toHaveBeenCalledWith('/meals/plan/2026-10-20/dinner', expect.objectContaining({
      data: { base: { recipe_id: null, title: 'Tacos', note: null } },
      headers: { 'Idempotency-Key': expect.any(String) },
    }))
    expect(await allWrites()).toEqual([])
  })
})
