import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useOfflineSync } from '../hooks/useOfflineSync'
import { allWrites, clearWrites, putWrite } from '../lib/idb'
import { offlineWrite, refreshPending, replay, useOffline } from '../lib/offline'
import { useAuthStore, type User } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import ShoppingTab from '../pages/meals/ShoppingTab'
import TodosTab from '../pages/chores/TodosTab'
import { MEMBERS } from '../pages/chores/fixtures'
import OfflineStatus from './OfflineStatus'

const networkError = () => Object.assign(new Error('Network Error'), { isAxiosError: true, request: {} })
const item = (id: string, name: string, over: object = {}) => ({ id, name, quantity: null, source: 'manual', recipe_id: null,
  recipe_title: null, week_start: null, checked: false, checked_at: null, checked_by: null, in_pantry: null, ...over })

function Shell() {
  useOfflineSync()
  return <><OfflineStatus /><ShoppingTab /></>
}

describe('offline banner, sync and conflicts', () => {
  beforeEach(() => {
    globalThis.indexedDB = new IDBFactory()
    useOffline.setState({ online: true, pending: [], syncing: false, signInNeeded: false })
    useAuthStore.getState().setUser({ id: 'kid', display_name: 'Kid', role: 'member' } as User)
  })
  afterEach(async () => {
    await replay()  // join any detached useOfflineSync replay before replacing IndexedDB in the next test
    await clearWrites()
    await refreshPending()
    useAuthStore.getState().clearUser()
    vi.restoreAllMocks()
  })

  it('shows nothing when online with nothing waiting', () => {
    const { container } = render(<QueryClientProvider client={new QueryClient()}><OfflineStatus /></QueryClientProvider>)
    expect(container.textContent).toBe('')
  })

  it('ticks an item off while offline, shows it, then syncs when the connection is back', async () => {
    const patch = vi.fn()
    let reachable = false
    mockApi({
      'GET /meals/shopping': [item('s1', 'Milk')],
      'PATCH /meals/shopping/s1': (body: unknown) => { if (!reachable) throw networkError(); patch(body); return item('s1', 'Milk', { checked: true }) },
    })
    renderApp(<Shell />)
    fireEvent.click(await screen.findByLabelText('Bought: Milk'))
    expect(await screen.findByText(/You're offline/)).toBeTruthy()
    expect(await screen.findByText('(1 waiting)')).toBeTruthy()
    expect((screen.getByLabelText('Not bought: Milk') as HTMLInputElement).checked).toBe(true)  // shown at once
    reachable = true
    await act(async () => { window.dispatchEvent(new Event('online')) })
    await waitFor(() => expect(patch).toHaveBeenCalled())
    expect(patch.mock.calls[0][0]).toEqual({ checked: true, base: { name: 'Milk', quantity: null, checked: false } })
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
    expect(await allWrites()).toEqual([])
  })

  it('adds an item offline and shows it right away', async () => {
    mockApi({ 'GET /meals/shopping': [], 'POST /meals/shopping': () => { throw networkError() } })
    renderApp(<Shell />)
    fireEvent.change(await screen.findByLabelText('New item'), { target: { value: 'Coffee' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Coffee')).toBeTruthy()
    expect((await allWrites()).map((w) => w.label)).toEqual(['Add Coffee to the list'])
  })

  it('ticks a to-do offline, remembering the to-do as it was', async () => {
    mockApi({
      'GET /users/': MEMBERS,
      'GET /todos': [{ id: 't1', title: 'Buy a card', notes: null, assigned_to: null, due_date: null, done: false, completed_by: null, created_by: 'kid' }],
      'PATCH /todos/t1': () => { throw networkError() },
    })
    renderApp(<TodosTab />)
    fireEvent.click(await screen.findByLabelText('Done: Buy a card'))
    await waitFor(async () => expect(await allWrites()).toHaveLength(1))
    const [w] = await allWrites()
    expect(w).toMatchObject({ label: 'Tick off to-do: Buy a card', local: { done: true },
      body: { done: true, base: { title: 'Buy a card', notes: null, assigned_to: null, due_date: null, done: false } } })
  })

  it('a conflict asks: keep mine, keep theirs, or merge', async () => {
    useOffline.setState({ online: false })
    mockApi({ 'GET /meals/shopping': [item('s1', 'Milk')] })
    await offlineWrite({ method: 'patch', url: '/meals/shopping/s1', body: { checked: true }, label: 'Tick off Milk',
      refresh: [['shopping']], base: { name: 'Milk', quantity: null, checked: false }, local: { checked: true } })
    useOffline.setState({ online: true })
    const sent: unknown[] = []
    let refuse = true
    mockApi({
      'GET /meals/shopping': [item('s1', 'Milk', { quantity: '2 gal' })],
      'PATCH /meals/shopping/s1': (body: unknown) => {
        if (refuse) throw apiError(409, { message: 'Someone else changed this while you were offline', fields: ['quantity'],
          current: { name: 'Milk', quantity: '2 gal', checked: false } } as never)
        sent.push(body)
        return item('s1', 'Milk', { checked: true })
      },
    })
    renderApp(<Shell />)
    fireEvent.click(await screen.findByRole('button', { name: '1 needs a decision' }))
    const dialog = screen.getByRole('dialog', { name: 'Offline change' })
    expect(dialog.textContent).toContain('Tick off Milk')
    expect(dialog.textContent).toContain('Changed by someone else: quantity')
    refuse = false
    fireEvent.click(screen.getByRole('button', { name: 'Merge' }))
    await waitFor(() => expect(sent).toEqual([{ checked: true }]))  // their quantity stays; my tick lands
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('an already-done chore can only be dropped, and a refused write can be discarded', async () => {
    await putWrite({ id: 'a', method: 'post', url: '/chores/instances/c1/complete', label: 'Finish: Dishes', createdAt: 1, refresh: [],
      conflict: { message: 'This chore is already done or was missed', fields: [] } })
    await putWrite({ id: 'b', method: 'post', url: '/meals/shopping', body: { name: 'x' }, label: 'Add x', createdAt: 2, refresh: [],
      error: 'Viewers can’t change meals' })
    await refreshPending()
    mockApi({ 'GET /meals/shopping': [] })
    renderApp(<Shell />)
    fireEvent.click(await screen.findByRole('button', { name: '2 need a decision' }))
    expect(screen.queryByRole('button', { name: 'Keep mine' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'OK, drop mine' }))
    fireEvent.click(await screen.findByRole('button', { name: '1 needs a decision' }))
    expect(screen.getByRole('dialog').textContent).toContain('Viewers can’t change meals')
    fireEvent.click(screen.getByRole('button', { name: 'Discard' }))
    await waitFor(async () => expect(await allWrites()).toEqual([]), { timeout: 5_000 })
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull(), { timeout: 5_000 })
  })

  it('asks to sign in again when the session lapsed, and offers Sync now', async () => {
    await putWrite({ id: 'a', method: 'post', url: '/meals/shopping', body: { name: 'x' }, label: 'Add x', createdAt: 1, refresh: [] })
    let calls = 0
    mockApi({ 'GET /meals/shopping': [], 'POST /meals/shopping': () => { calls++; throw apiError(401, 'Not authenticated') } })
    renderApp(<Shell />)
    expect(await screen.findByText('🔑 Sign in again to save 1 change.')).toBeTruthy()
    useOffline.setState({ signInNeeded: false })
    fireEvent.click(await screen.findByRole('button', { name: 'Sync now' }))
    await waitFor(() => expect(calls).toBe(2))
  })
})
