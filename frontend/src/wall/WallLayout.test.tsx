import { act, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as wallModule from '../api/wall'
import type { WallSession } from '../api/wall'

const getWallSessionMock = () => wallModule.getWallSession
import WallLayout from './WallLayout'

const { SESSION } = vi.hoisted(() => ({
  SESSION: {
    device: 'Kitchen', family_name: 'Test', idle_timeout_seconds: 300, timezone: 'America/Detroit',
    sleep: { enabled: false, off: '22:00', on: '06:30' },
    dashboard: { pages: [{ name: 'Kitchen', duration_seconds: 45, widgets: [{ key: 'events', size: 'wide' }] }] },
  } satisfies WallSession,
}))

const wallApi = vi.hoisted(() => ({
  listener: null as null | (() => void),
}))

const wallCycle = vi.hoisted(() => ({
  props: [] as unknown[],
}))

vi.mock('../api/wall', () => ({
  pairWall: vi.fn(),
  getWallSession: vi.fn(async () => ({ ...SESSION })),
  onWallUnauthorized: vi.fn((listener: () => void) => {
    const id = setTimeout(() => {
      wallApi.listener = listener
    }, 0)
    return () => {
      clearTimeout(id)
      if (wallApi.listener === listener) wallApi.listener = null
    }
  }),
}))
vi.mock('./WallSevenDayStrip', () => ({ default: () => <div>seven-day strip</div> }))
vi.mock('./WallProgress', () => ({ default: () => <div>progress</div> }))
vi.mock('./WallBirthdays', () => ({ default: () => null }))
vi.mock('./WallClock', () => ({ default: () => <div>clock</div> }))
vi.mock('./WallSlideshow', () => ({ default: () => <div>slideshow</div> }))
vi.mock('./WallRoutines', () => ({ default: () => null }))
vi.mock('./WallCycle.tsx', () => ({ default: (props: unknown) => { wallCycle.props.push(props); return <div>configured wall dashboard</div> } }))
vi.mock('./useWallWebSocket', () => ({ useWallWebSocket: () => {} }))

describe('WallLayout revocation (#10)', () => {
  beforeEach(() => {
    wallApi.listener = null
    wallCycle.props = []
  })

  it('drops back to the pairing screen and clears wall data on a 401', async () => {
    const client = new QueryClient()
    client.setQueryData(['wall-events', 'a', 'b'], [{ id: 'e1' }])
    client.setQueryData(['wall-progress'], [{ user_id: 'u1' }])
    client.setQueryData(['unrelated'], 1)

    render(
      <QueryClientProvider client={client}>
        <WallLayout />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('configured wall dashboard')).toBeTruthy()
    await waitFor(() => expect(wallApi.listener).not.toBeNull())

    act(() => wallApi.listener!())

    expect(await screen.findByText(/isn't paired yet/)).toBeTruthy()
    expect(client.getQueryData(['wall-events', 'a', 'b'])).toBeUndefined()
    expect(client.getQueryData(['wall-progress'])).toBeUndefined()
    expect(client.getQueryData(['unrelated'])).toBe(1)
  })

  it('switches to the idle screen after the timeout and wakes on touch', async () => {
    const { getWallSession } = await import('../api/wall')
    vi.mocked(getWallSession).mockResolvedValue({ ...SESSION, idle_timeout_seconds: 0.05 })
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <WallLayout />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('configured wall dashboard')).toBeTruthy()
    expect(await screen.findByText('slideshow')).toBeTruthy()
    expect(screen.queryByText('configured wall dashboard')).toBeNull()
    act(() => {
      window.dispatchEvent(new Event('mousemove'))
    })
    expect(await screen.findByText('configured wall dashboard')).toBeTruthy()
  })

  it('shows the configured dashboard on the paired wall board', async () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <WallLayout />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('configured wall dashboard')).toBeTruthy()
    expect(wallCycle.props.at(-1)).toMatchObject({ dashboard: SESSION.dashboard, timeZone: 'America/Detroit' })
    expect(screen.queryByText('progress')).toBeNull()
    expect(screen.queryByText('clock')).toBeNull()
  })

  it('pairs from a ?token= link and removes the token from the address bar', async () => {
    const { pairWall } = await import('../api/wall')
    window.history.pushState({}, '', '/wall?token=secret-token')
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <WallLayout />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('configured wall dashboard')).toBeTruthy()
    expect(vi.mocked(pairWall)).toHaveBeenCalledWith('secret-token')
    expect(window.location.search).toBe('')
  })

  describe('sleep schedule (Phase 3b)', () => {
    afterEach(() => {
      vi.useRealTimers()
      vi.mocked(getWallSessionMock()).mockImplementation(async () => ({ ...SESSION }))
    })

    async function bootAt(iso: string, sleep: object, timezone: string) {
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(new Date(iso))
      vi.mocked(getWallSessionMock()).mockImplementation(async () => ({ ...SESSION, timezone, sleep: sleep as typeof SESSION.sleep }))
      render(
        <QueryClientProvider client={new QueryClient()}>
          <WallLayout />
        </QueryClientProvider>,
      )
    }

    it('goes dark during the schedule and lights up on touch', async () => {
      // 23:00 in Detroit (EDT): inside 22:00-06:30.
      await bootAt('2026-10-21T03:00:00Z', { enabled: true, off: '22:00', on: '06:30' }, 'America/Detroit')
      expect(await screen.findByTestId('wall-asleep')).toBeTruthy()
      expect(screen.queryByText('configured wall dashboard')).toBeNull()
      act(() => {
        window.dispatchEvent(new Event('touchstart'))
      })
      expect(await screen.findByText('configured wall dashboard')).toBeTruthy()
    })

    it('follows the family timezone, not the device zone', async () => {
      // 03:00Z is 23:00 in Detroit (inside 22:00-02:00 there) but 04:00 in
      // London (outside it). The family is in London, so the screen stays on.
      await bootAt('2026-10-21T03:00:00Z', { enabled: true, off: '22:00', on: '02:00' }, 'Europe/London')
      expect(await screen.findByText('configured wall dashboard')).toBeTruthy()
      expect(screen.queryByTestId('wall-asleep')).toBeNull()
    })

    it('stays on when the schedule is disabled', async () => {
      await bootAt('2026-10-21T03:00:00Z', { enabled: false, off: '22:00', on: '06:30' }, 'America/Detroit')
      expect(await screen.findByText('configured wall dashboard')).toBeTruthy()
    })
  })
})
