import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '../../stores/auth'
import { apiError } from '../../test/api'
import { renderApp } from '../../test/render'
import ChoresPage from './ChoresPage'
import { choresApi, signIn } from './fixtures'

const tab = (name: string) => fireEvent.click(screen.getByRole('tab', { name }))

describe('ChoresPage', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('shows Manage to admins only', () => {
    choresApi()
    signIn('kid', 'member')
    const { unmount } = renderApp(<ChoresPage />)
    expect(screen.queryByRole('tab', { name: 'Manage' })).toBeNull()
    unmount()
    signIn('mom', 'admin')
    renderApp(<ChoresPage />)
    expect(screen.getByRole('tab', { name: 'Manage' })).toBeTruthy()
  })

  describe('Today', () => {
    it("lists my chores and what's up for grabs, with my stats", async () => {
      choresApi()
      signIn('kid', 'member')
      renderApp(<ChoresPage />)
      expect(await screen.findByText('15')).toBeTruthy()
      expect(screen.getByText('🔥 4-day streak')).toBeTruthy()
      expect(screen.getByText('Feed the cat')).toBeTruthy()
      expect(screen.getByText('Take out bins')).toBeTruthy()
    })

    it('completes, claims and undoes', async () => {
      const calls = choresApi()
      signIn('kid', 'member')
      renderApp(<ChoresPage />)
      fireEvent.click(await screen.findByRole('button', { name: 'Done: Feed the cat' }))
      await waitFor(() => expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1))
      fireEvent.click(await screen.findByRole('button', { name: "I'll do it: Take out bins" }))
      await waitFor(() => expect(calls.filter((c) => c.method === 'POST')).toHaveLength(2))
      fireEvent.click(await screen.findByRole('button', { name: 'Undo: Dishes' }))
      await waitFor(() => expect(calls.filter((c) => c.method === 'POST').map((c) => c.url)).toEqual([
        '/chores/instances/a/complete', '/chores/instances/b/claim', '/chores/instances/d/undo']))
    })

    it("shows the server's reason when an action fails", async () => {
      choresApi({ 'POST /chores/instances/a/complete': () => { throw apiError(409, 'This chore is already done or was missed') } })
      signIn('kid', 'member')
      renderApp(<ChoresPage />)
      fireEvent.click(await screen.findByRole('button', { name: 'Done: Feed the cat' }))
      expect(await screen.findByText('This chore is already done or was missed')).toBeTruthy()
    })

    it('viewers see the day but get no buttons', async () => {
      choresApi()
      signIn('gm', 'viewer')
      renderApp(<ChoresPage />)
      expect(await screen.findByText('Everyone today')).toBeTruthy()
      expect(screen.queryByText('My chores')).toBeNull()
      expect(screen.queryByRole('button', { name: /Done:/ })).toBeNull()
    })
  })

  describe('To-dos', () => {
    it('adds, ticks off and deletes', async () => {
      const calls = choresApi({
        'GET /todos': [{ id: 't1', title: 'Buy a card', notes: null, assigned_to: 'kid', due_date: '2026-10-14',
          done: false, completed_by: null, created_by: 'kid' }],
        'POST /todos': { id: 't2' }, 'PATCH /todos/t1': { id: 't1' }, 'DELETE /todos/t1': null,
      })
      signIn('kid', 'member')
      renderApp(<ChoresPage />)
      tab('To-dos')
      expect(await screen.findByText('Buy a card')).toBeTruthy()
      expect(screen.getByText('Kid · due 2026-10-14')).toBeTruthy()
      fireEvent.change(screen.getByLabelText('New to-do'), { target: { value: 'Return library books' } })
      fireEvent.change(screen.getByLabelText('For'), { target: { value: 'mom' } })
      fireEvent.click(screen.getByRole('button', { name: 'Add' }))
      fireEvent.click(screen.getByLabelText('Done: Buy a card'))
      fireEvent.click(screen.getByRole('button', { name: 'Delete Buy a card' }))
      await waitFor(() => expect(calls.filter((c) => c.method !== 'GET')).toHaveLength(3))
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ title: 'Return library books', assigned_to: 'mom', due_date: null })
      expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ done: true })
    })

    it('says when there is nothing to do', async () => {
      choresApi({ 'GET /todos': [] })
      signIn('kid', 'member')
      renderApp(<ChoresPage />)
      tab('To-dos')
      expect(await screen.findByText('Nothing to do. 🎉')).toBeTruthy()
    })
  })

  describe('Routines', () => {
    const run = (assigned_to: string) => [{
      id: 'r1', name: 'Morning', assigned_to, assigned_name: 'Kid', assigned_color: null, start_time: '07:00',
      steps: [
        { instance_id: 's1', template_id: 'x1', title: 'Get dressed', minutes: 5, points: 1, status: 'completed' },
        { instance_id: 's2', template_id: 'x2', title: 'Brush teeth', minutes: 3, points: 1, status: 'pending' },
      ],
    }]

    it('ticks steps off and back on', async () => {
      const calls = choresApi({ 'GET /routines/today': run('kid'), 'POST /chores/instances/s2/complete': {}, 'POST /chores/instances/s1/undo': {} })
      signIn('kid', 'member')
      renderApp(<ChoresPage />)
      tab('Routines')
      expect(await screen.findByText('Kid · 07:00 · 1/2')).toBeTruthy()
      fireEvent.click(screen.getByLabelText('Brush teeth done'))
      await waitFor(() => expect(calls.some((c) => c.url === '/chores/instances/s2/complete')).toBe(true))
      await waitFor(() => expect((screen.getByLabelText('Get dressed done') as HTMLInputElement).disabled).toBe(false))
      fireEvent.click(screen.getByLabelText('Get dressed done'))
      await waitFor(() => expect(calls.some((c) => c.url === '/chores/instances/s1/undo')).toBe(true))
    })

    it("can't tick someone else's routine", async () => {
      choresApi({ 'GET /routines/today': run('kid') })
      signIn('sib', 'member')
      renderApp(<ChoresPage />)
      tab('Routines')
      expect(((await screen.findByLabelText('Brush teeth done')) as HTMLInputElement).disabled).toBe(true)
    })

    it('says when there are none', async () => {
      choresApi({ 'GET /routines/today': [] })
      signIn('kid', 'member')
      renderApp(<ChoresPage />)
      tab('Routines')
      expect(await screen.findByText('No routines today.')).toBeTruthy()
    })
  })

  it('shows family points and recent completions', async () => {
    choresApi({
      'GET /chores/points': [{ user_id: 'kid', display_name: 'Kid', points: 15 }, { user_id: 'mom', display_name: 'Mom', points: 0 }],
      'GET /chores/log': [{ id: 'l1', title: 'Dishes', completed_by: 'kid', credited_to: 'kid', points: 5,
        completed_at: '2026-10-12T15:00:00Z', undone_at: null }],
    })
    signIn('kid', 'member')
    renderApp(<ChoresPage />)
    tab('Points & history')
    expect(await screen.findByText('Dishes — Kid')).toBeTruthy()
  })
})
