import { render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/api'
import WallSevenDayStrip from './WallSevenDayStrip'

vi.mock('./useWallWebSocket', () => ({ useWallWebSocket: () => {} }))

// Monday 12 Oct 2026, 10:00 in Detroit (vitest pins TZ).
const NOW = new Date(2026, 9, 12, 10, 0)
const local = (d: number, h: number, m = 0) => new Date(2026, 9, d, h, m).toISOString()
const ev = (id: string, title: string, start: string, end: string, all_day = false) =>
  ({ id, source_id: 's', title, start_dt: start, end_dt: end, all_day, location: null, description: null,
     created_by: null, source_color_hex: '#4F46E5' })

function renderStrip() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><WallSevenDayStrip /></QueryClientProvider>)
}

const column = (header: string) => screen.getByText(header).parentElement as HTMLElement

describe('WallSevenDayStrip', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(NOW)
  })
  afterEach(() => vi.useRealTimers())

  it('shows seven days from today and highlights today', async () => {
    mockApi({ 'GET /wall/events': [] })
    renderStrip()
    const headers = ['Mon 12', 'Tue 13', 'Wed 14', 'Thu 15', 'Fri 16', 'Sat 17', 'Sun 18']
    for (const h of headers) expect(screen.getByText(h)).toBeTruthy()
    expect(screen.getByText('Mon 12').className).toContain('bg-white')
    expect(screen.getByText('Tue 13').className).not.toContain('bg-white')
  })

  it('puts all-day events first, then timed ones by start time', async () => {
    mockApi({
      'GET /wall/events': [
        ev('t2', 'Piano', local(12, 17), local(12, 18)),
        ev('t1', 'Dentist', local(12, 9, 30), local(12, 10)),
        ev('a', 'No school', '2026-10-12T00:00:00+00:00', '2026-10-13T00:00:00+00:00', true),
      ],
    })
    renderStrip()
    await screen.findByText('Piano')
    const titles = within(column('Mon 12')).getAllByText(/Piano|Dentist|No school/).map((n) => n.textContent)
    expect(titles).toEqual(['No school', 'Dentist', 'Piano'])
    expect(within(column('Mon 12')).getByText('All day')).toBeTruthy()
    expect(within(column('Mon 12')).getByText('09:30')).toBeTruthy()
  })

  it('shows an overnight event on both days', async () => {
    mockApi({ 'GET /wall/events': [ev('n', 'Sleepover', local(16, 19), local(17, 9))] })
    renderStrip()
    await screen.findAllByText('Sleepover')
    expect(within(column('Fri 16')).getByText('Sleepover')).toBeTruthy()
    expect(within(column('Sat 17')).getByText('Sleepover')).toBeTruthy()
  })

  it('caps a day at five events with a "+N more" note', async () => {
    mockApi({ 'GET /wall/events': Array.from({ length: 7 }, (_, i) => ev(`e${i}`, `Thing ${i}`, local(13, 8 + i), local(13, 9 + i))) })
    renderStrip()
    await screen.findByText('Thing 0')
    expect(within(column('Tue 13')).getAllByText(/Thing \d/)).toHaveLength(5)
    expect(within(column('Tue 13')).getByText('+2 more')).toBeTruthy()
  })
})
