import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../../stores/auth'
import { apiError } from '../../test/api'
import { renderApp } from '../../test/render'
import ChoresPage from './ChoresPage'
import { choresApi, signIn } from './fixtures'

const TEMPLATE = { id: 'c1', title: 'Feed the cat', description: null, points: 5, assignment: 'assigned', assigned_to: 'kid',
  repeat: { every: 'day', interval: 1 }, start_date: '2026-10-01', is_active: true }
const ROUTINE = { id: 'r1', name: 'Morning', assigned_to: 'kid', start_time: '07:00', repeat: { every: 'day' }, start_date: '2026-10-01',
  steps: [{ id: 'x1', title: 'Get dressed', minutes: 5, points: 1 }, { id: 'x2', title: 'Brush teeth', minutes: 3, points: 2 }] }

function manage(extra: Record<string, unknown> = {}) {
  const calls = choresApi({
    'GET /chores/templates': [TEMPLATE], 'GET /routines': [ROUTINE],
    'GET /chores/by-user': [{ user_id: 'kid', display_name: 'Kid', pending: 2, completed: 1, missed: 0 }],
    ...extra,
  })
  signIn('mom', 'admin')
  renderApp(<ChoresPage />)
  fireEvent.click(screen.getByRole('tab', { name: 'Manage' }))
  return calls
}

describe('Manage', () => {
  afterEach(() => {
    useAuthStore.getState().clearUser()
    vi.unstubAllGlobals()
  })

  it('shows counts by person and the chores and routines in words', async () => {
    manage()
    expect(await screen.findByText('Kid · Every day · 5 pts')).toBeTruthy()
    const row = screen.getByRole('cell', { name: 'Kid' }).closest('tr') as HTMLElement
    expect(within(row).getAllByRole('cell').map((c) => c.textContent)).toEqual(['Kid', '2', '1', '0'])
    expect(screen.getByText('Kid · 07:00 · Get dressed → Brush teeth')).toBeTruthy()
  })

  it('adds a weekly chore for someone', async () => {
    const calls = manage({ 'POST /chores/templates': TEMPLATE })
    fireEvent.click(await screen.findByRole('button', { name: 'Add chore' }))
    const form = screen.getByRole('form', { name: 'New chore' })
    fireEvent.change(within(form).getByLabelText('Chore'), { target: { value: 'Water plants' } })
    fireEvent.change(within(form).getByLabelText('Points'), { target: { value: '3' } })
    fireEvent.change(within(form).getByLabelText('Who'), { target: { value: 'kid' } })
    fireEvent.change(within(form).getByLabelText('Repeats'), { target: { value: 'week' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Mon' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Thu' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Save chore' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      title: 'Water plants', points: 3, assignment: 'assigned', assigned_to: 'kid',
      repeat: { every: 'week', interval: 1, weekdays: ['mo', 'th'] },
    })
  })

  it('edits and stops a chore', async () => {
    const calls = manage({ 'PATCH /chores/templates/c1': TEMPLATE, 'DELETE /chores/templates/c1': null })
    vi.stubGlobal('confirm', vi.fn(() => true))
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Feed the cat' }))
    const form = screen.getByRole('form', { name: 'Edit Feed the cat' })
    fireEvent.change(within(form).getByLabelText('Who'), { target: { value: '' } })
    fireEvent.change(within(form).getByLabelText('Repeats'), { target: { value: 'month' } })
    fireEvent.change(within(form).getByLabelText('Every how many'), { target: { value: '2' } })
    fireEvent.change(within(form).getByLabelText('Day of the month'), { target: { value: '-1' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save chore' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(calls.find((c) => c.method === 'PATCH')?.body).toMatchObject({
      assignment: 'claimable', assigned_to: null, repeat: { every: 'month', interval: 2, month_day: -1 }, start_date: '2026-10-01',
    })
    fireEvent.click(screen.getByRole('button', { name: 'Stop Feed the cat' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
  })

  it('reorders routine steps and saves them in the new order', async () => {
    const calls = manage({ 'PATCH /routines/r1': ROUTINE })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Morning' }))
    const form = screen.getByRole('form', { name: 'Edit Morning' })
    fireEvent.click(within(form).getByRole('button', { name: 'Move step 2 up' }))
    fireEvent.click(within(form).getByRole('button', { name: '+ Step' }))
    fireEvent.change(within(form).getByLabelText('Step 3'), { target: { value: 'Pack bag' } })
    fireEvent.change(within(form).getByLabelText('Step 3 points'), { target: { value: '4' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Move step 3 up' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Move step 1 down' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Save routine' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    const body = calls.find((c) => c.method === 'PATCH')?.body as { steps: { id?: string; title: string; points: number }[] }
    expect(body.steps.map((s) => [s.id, s.title])).toEqual([[undefined, 'Pack bag'], ['x2', 'Brush teeth'], ['x1', 'Get dressed']])
    expect(body.steps[0].points).toBe(4)
  })

  it('creates a routine, skipping empty steps', async () => {
    const calls = manage({ 'POST /routines': ROUTINE })
    fireEvent.click(await screen.findByRole('button', { name: 'Add routine' }))
    const form = screen.getByRole('form', { name: 'New routine' })
    fireEvent.change(within(form).getByLabelText('Routine'), { target: { value: 'Bedtime' } })
    fireEvent.change(within(form).getByLabelText('Starts at'), { target: { value: '19:30' } })
    fireEvent.change(within(form).getByLabelText('Step 1'), { target: { value: 'Bath' } })
    fireEvent.change(within(form).getByLabelText('Step 1 minutes'), { target: { value: '20' } })
    fireEvent.click(within(form).getByRole('button', { name: '+ Step' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Remove step 2' }))
    fireEvent.click(within(form).getByRole('button', { name: '+ Step' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Save routine' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      name: 'Bedtime', start_time: '19:30', assigned_to: null, steps: [{ title: 'Bath', minutes: 20, points: 1 }],
    })
  })

  it('stops a routine after confirming', async () => {
    const calls = manage({ 'DELETE /routines/r1': null })
    vi.stubGlobal('confirm', vi.fn(() => true))
    fireEvent.click(await screen.findByRole('button', { name: 'Stop Morning' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url === '/routines/r1')).toBe(true))
  })

  it('shows why a save failed, and cancel closes the form', async () => {
    manage({ 'POST /chores/templates': () => { throw apiError(400, "That person isn't in this family") } })
    fireEvent.click(await screen.findByRole('button', { name: 'Add chore' }))
    const form = screen.getByRole('form', { name: 'New chore' })
    fireEvent.change(within(form).getByLabelText('Chore'), { target: { value: 'x' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save chore' }))
    expect(await within(form).findByText("That person isn't in this family")).toBeTruthy()
    fireEvent.click(within(form).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('form', { name: 'New chore' })).toBeNull()
  })
})
