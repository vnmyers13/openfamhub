import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import RequireAdmin from './RequireAdmin'

function user(role: string): User {
  return {
    id: 'u1', display_name: 'Test', role, color_hex: '#000000', ui_mode: 'dark',
    avatar_type: null, avatar_value: null, family_id: 'f1',
  }
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/dashboard" element={<div>dashboard</div>} />
        <Route element={<RequireAdmin />}>
          <Route path="/admin/calendars" element={<div>calendar settings</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('RequireAdmin (#14)', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('renders admin pages for admins', () => {
    useAuthStore.getState().setUser(user('admin'))
    renderAt('/admin/calendars')
    expect(screen.getByText('calendar settings')).toBeTruthy()
  })

  it.each(['member', 'viewer'])('sends a %s to the dashboard', (role) => {
    useAuthStore.getState().setUser(user(role))
    renderAt('/admin/calendars')
    expect(screen.getByText('dashboard')).toBeTruthy()
    expect(screen.queryByText('calendar settings')).toBeNull()
  })

  it('renders nothing until the signed-in user is known', () => {
    renderAt('/admin/calendars')
    expect(screen.queryByText('calendar settings')).toBeNull()
    expect(screen.queryByText('dashboard')).toBeNull()
  })
})
