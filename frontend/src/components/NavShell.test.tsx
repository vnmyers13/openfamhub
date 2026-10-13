import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { mockApi } from '../test/api'
import NavShell from './NavShell'
import PasswordPrompt from './PasswordPrompt'

function signIn(role: string, admin_unlocked = true) {
  useAuthStore.getState().setUser({
    id: 'u', display_name: 'Mom', role, color_hex: '#4F46E5', ui_mode: 'standard',
    avatar_type: 'emoji', avatar_value: '🦊', family_id: 'f', admin_unlocked,
  } as User)
}

function renderShell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route element={<NavShell />}>
            <Route path="/dashboard" element={<div>home page</div>} />
          </Route>
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
        <PasswordPrompt />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('NavShell', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('shows admin links to admins only', () => {
    mockApi({})
    signIn('admin')
    const { unmount } = renderShell()
    expect(screen.getAllByText('Wall displays').length).toBeGreaterThan(0)
    expect(screen.getByText('home page')).toBeTruthy()
    unmount()

    signIn('member')
    renderShell()
    expect(screen.queryByText('Wall displays')).toBeNull()
  })

  it('offers "Unlock admin" to a PIN-signed-in admin and opens the password prompt', async () => {
    mockApi({})
    signIn('admin', false)
    renderShell()
    fireEvent.click(screen.getByText(/Unlock admin/))
    expect(await screen.findByRole('dialog')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  })

  it('signs out and returns to the login page', async () => {
    const calls = mockApi({ 'POST /auth/logout': { ok: true } })
    signIn('member')
    renderShell()
    fireEvent.click(screen.getAllByRole('button', { name: /logout/i })[0])
    expect(await screen.findByText('login page')).toBeTruthy()
    expect(calls.some((c) => c.url === '/auth/logout')).toBe(true)
    await waitFor(() => expect(useAuthStore.getState().user).toBeNull())
  })

  it('shows the running build in Help & About', async () => {
    mockApi({ 'GET /health': { build: '0.77', commit: 'abc1234' } })
    signIn('member')
    renderShell()
    expect(await screen.findByText('OpenFamHub 0.77')).toBeTruthy()
  })
})
