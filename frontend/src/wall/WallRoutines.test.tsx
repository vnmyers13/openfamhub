import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiError, mockApi } from '../test/api'
import WallRoutines from './WallRoutines'

const step = (n: number, title: string, minutes: number, status = 'pending') =>
  ({ instance_id: `i${n}`, template_id: `t${n}`, title, minutes, points: 1, status })
const MORNING = {
  id: 'r1', name: 'Morning', assigned_to: 'kid', assigned_name: 'Kid', assigned_color: '#f59e0b', start_time: '07:00',
  steps: [step(1, 'Get dressed', 5), step(2, 'Breakfast', 15), step(3, 'Brush teeth', 3)],
}

function renderAt(iso: string, runs: object[], timeZone = 'America/Detroit') {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(iso))
  const calls = mockApi({ 'GET /wall/routines': runs })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return { calls, client, ...render(<QueryClientProvider client={client}><WallRoutines timeZone={timeZone} /></QueryClientProvider>) }
}

describe('WallRoutines', () => {
  afterEach(() => vi.useRealTimers())

  it('shows the current step with its countdown and progress', async () => {
    // 07:06:30 in Detroit: step 2 (Breakfast) runs 07:05-07:20.
    renderAt('2026-10-20T11:06:30Z', [{ ...MORNING, steps: [step(1, 'Get dressed', 5, 'completed'), MORNING.steps[1], MORNING.steps[2]] }])
    expect(await screen.findByText('Breakfast', { selector: 'p' })).toBeTruthy()
    expect(screen.getByLabelText('time left').textContent).toBe('13:30')
    expect(screen.getByLabelText('1 of 3 done')).toBeTruthy()
    expect(screen.getByText('✓ Get dressed')).toBeTruthy()
  })

  it('gives a heads-up in the half hour before it starts', async () => {
    renderAt('2026-10-20T10:45:00Z', [MORNING]) // 06:45
    expect(await screen.findByText('Starts in 15 min')).toBeTruthy()
  })

  it('stays out of the way otherwise', async () => {
    const { container } = renderAt('2026-10-20T09:00:00Z', [MORNING]) // 05:00, too early
    await new Promise((r) => setTimeout(r, 20))
    expect(container.querySelector('[data-testid="wall-routine"]')).toBeNull()
    expect(screen.getByText('No routine right now.')).toBeTruthy()  // the card isn't left blank
  })

  it('disappears once every step is done', async () => {
    const all = { ...MORNING, steps: MORNING.steps.map((s) => ({ ...s, status: 'completed' })) }
    const { container } = renderAt('2026-10-20T11:06:30Z', [all])
    await new Promise((r) => setTimeout(r, 20))
    expect(container.querySelector('[data-testid="wall-routine"]')).toBeNull()
  })

  it('uses the family timezone', async () => {
    // 11:06:30Z is 12:06 in London: the routine is long over there.
    const { container } = renderAt('2026-10-20T11:06:30Z', [MORNING], 'Europe/London')
    await new Promise((r) => setTimeout(r, 20))
    expect(container.querySelector('[data-testid="wall-routine"]')).toBeNull()
  })

  it('checks off the current step from the wall', async () => {
    const { calls } = renderAt('2026-10-20T11:06:30Z', [
      { ...MORNING, steps: [step(1, 'Get dressed', 5, 'completed'), MORNING.steps[1], MORNING.steps[2]] },
    ])

    fireEvent.click(await screen.findByRole('button', { name: 'Done with Breakfast' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url === '/wall/routines/steps/i2/complete')).toBe(true))
  })

  it('shows an error when the wall cannot complete a step', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-20T11:06:30Z'))
    mockApi({
      'GET /wall/routines': [{ ...MORNING, steps: [step(1, 'Get dressed', 5, 'completed'), MORNING.steps[1], MORNING.steps[2]] }],
      'POST /wall/routines/steps/i2/complete': () => { throw apiError(403, 'This routine step is not assigned to a person') },
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(<QueryClientProvider client={client}><WallRoutines timeZone="America/Detroit" /></QueryClientProvider>)

    fireEvent.click(await screen.findByRole('button', { name: 'Done with Breakfast' }))

    expect(await screen.findByText('This routine step is not assigned to a person')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Done with Breakfast' })).toHaveProperty('disabled', false)
  })
})
