import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import App from './App'
import { useAuthStore } from './stores/auth'
import { apiError, mockApi } from './test/api'

const ADMIN = { id: 'mom', display_name: 'Mom', role: 'admin', color_hex: '#4F46E5', ui_mode: 'standard',
  avatar_type: null, avatar_value: null, family_id: 'f', admin_unlocked: true }

function boot(path: string) {
  window.history.pushState({}, '', path)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><App /></QueryClientProvider>)
}

describe('App boot', () => {
  // App's pages are lazy-loaded. The first test to open one would wait while
  // Vite compiles its whole module tree, which on a cold CI runner takes longer
  // than findBy's 1 s and failed there. Load them once, up front, so each test
  // measures routing, not compiling.
  beforeAll(async () => {
    await Promise.all([
      import('./pages/SetupWizard'), import('./pages/Dashboard'), import('./pages/admin/WallDisplays'), import('./wall/WallLayout'),
    ])
  }, 60_000)

  afterEach(() => {
    useAuthStore.getState().clearUser()
    window.history.pushState({}, '', '/')
  })

  it('sends a fresh install to the setup wizard', async () => {
    mockApi({ 'GET /auth/setup/status': { setup_complete: false } })
    boot('/')
    expect(await screen.findByText('Set up your family hub')).toBeTruthy()
  })

  it('sends a signed-out visitor to sign-in', async () => {
    mockApi({
      'GET /auth/setup/status': { setup_complete: true },
      'GET /auth/me': () => { throw apiError(401, 'Not authenticated') },
      'GET /auth/profiles': [],
    })
    boot('/calendar')
    expect(await screen.findByText('Sign in with your password')).toBeTruthy()
    expect(window.location.pathname).toBe('/login')
  })

  it('takes a signed-in member from the entry page to the dashboard', async () => {
    mockApi({
      'GET /auth/setup/status': { setup_complete: true },
      'GET /auth/me': ADMIN,
      'GET /calendar/events': [],
      'GET /calendar/sources': [],
    })
    boot('/')
    expect(await screen.findByText(/Good (morning|afternoon|evening), Mom!/)).toBeTruthy()
    expect(window.location.pathname).toBe('/dashboard')
  })

  it('keeps a signed-in member on the page they opened', async () => {
    mockApi({
      'GET /auth/setup/status': { setup_complete: true },
      'GET /auth/me': ADMIN,
      'GET /wall/devices': [],
    })
    boot('/admin/wall')
    expect(await screen.findByRole('heading', { name: 'Wall displays' })).toBeTruthy()
  })

  it("skips the user boot for the wall, which has its own device sign-in", async () => {
    const calls = mockApi({ 'GET /wall/session': () => { throw apiError(401, 'Display not paired') } })
    boot('/wall')
    expect(await screen.findByText(/isn't paired yet/)).toBeTruthy()
    expect(calls.some((c) => c.url.startsWith('/auth/'))).toBe(false)
  })
})
