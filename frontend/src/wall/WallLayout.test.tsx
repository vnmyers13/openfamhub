import { act, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WallLayout from './WallLayout'

const wallApi = vi.hoisted(() => ({
  listener: null as null | (() => void),
}))

vi.mock('../api/wall', () => ({
  pairWall: vi.fn(),
  getWallSession: vi.fn(async () => ({ device: 'Kitchen', family_name: 'Test', idle_timeout_seconds: 300 })),
  onWallUnauthorized: vi.fn((listener: () => void) => {
    wallApi.listener = listener
    return () => {
      if (wallApi.listener === listener) wallApi.listener = null
    }
  }),
}))
vi.mock('./WallSevenDayStrip', () => ({ default: () => <div>seven-day strip</div> }))
vi.mock('./WallMemberList', () => ({ default: () => <div>members</div> }))
vi.mock('./WallClock', () => ({ default: () => <div>clock</div> }))

describe('WallLayout revocation (#10)', () => {
  beforeEach(() => {
    wallApi.listener = null
  })

  it('drops back to the pairing screen and clears wall data on a 401', async () => {
    const client = new QueryClient()
    client.setQueryData(['wall-events', 'a', 'b'], [{ id: 'e1' }])
    client.setQueryData(['wall-members'], [{ id: 'u1' }])
    client.setQueryData(['unrelated'], 1)

    render(
      <QueryClientProvider client={client}>
        <WallLayout />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('seven-day strip')).toBeTruthy()
    expect(wallApi.listener).not.toBeNull()

    act(() => wallApi.listener!())

    expect(await screen.findByText(/isn't paired yet/)).toBeTruthy()
    expect(client.getQueryData(['wall-events', 'a', 'b'])).toBeUndefined()
    expect(client.getQueryData(['wall-members'])).toBeUndefined()
    expect(client.getQueryData(['unrelated'])).toBe(1)
  })

  it('switches to the idle screen after the timeout and wakes on touch', async () => {
    const { getWallSession } = await import('../api/wall')
    vi.mocked(getWallSession).mockResolvedValueOnce({ device: 'Kitchen', family_name: 'Test', idle_timeout_seconds: 0.05 })
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <WallLayout />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('seven-day strip')).toBeTruthy()
    await waitFor(() => expect(screen.queryByText('seven-day strip')).toBeNull())
    act(() => {
      window.dispatchEvent(new Event('mousemove'))
    })
    expect(await screen.findByText('seven-day strip')).toBeTruthy()
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
    expect(await screen.findByText('seven-day strip')).toBeTruthy()
    expect(vi.mocked(pairWall)).toHaveBeenCalledWith('secret-token')
    expect(window.location.search).toBe('')
  })
})

