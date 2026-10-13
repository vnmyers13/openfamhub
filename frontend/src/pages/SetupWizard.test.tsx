import { fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import SetupWizard from './SetupWizard'

const renderWizard = () => renderApp(<SetupWizard />, { path: '/setup', routes: { '/dashboard': 'dashboard page' } })

function fillIn(container: HTMLElement, { family = 'Myers', admin = 'Mom', password = 'securepassword123', pin = '' } = {}) {
  const [familyInput, adminInput, passwordInput, pinInput] = Array.from(container.querySelectorAll('input'))
  fireEvent.change(familyInput, { target: { value: family } })
  fireEvent.change(adminInput, { target: { value: admin } })
  fireEvent.change(passwordInput, { target: { value: password } })
  if (pinInput) fireEvent.change(pinInput, { target: { value: pin } })
}

describe('SetupWizard', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it("defaults the family timezone to this device's zone", () => {
    mockApi({})
    const { container } = renderWizard()
    const select = container.querySelector('select') as HTMLSelectElement
    // vitest pins TZ=America/Detroit, which isn't one of the old five US choices.
    expect(select.value).toBe('America/Detroit')
    expect(Array.from(select.options).map((o) => o.value)).toContain('Europe/London')
  })

  it('creates the family and signs the admin in', async () => {
    const calls = mockApi({ 'POST /auth/setup': { id: 'mom', display_name: 'Mom', role: 'admin', family_id: 'f' } })
    const { container } = renderWizard()
    fillIn(container, { pin: '2468' })
    fireEvent.change(container.querySelector('select')!, { target: { value: 'Europe/London' } })
    fireEvent.submit(container.querySelector('form')!)
    expect(await screen.findByText('dashboard page')).toBeTruthy()
    expect(calls.find((c) => c.url === '/auth/setup')?.body).toEqual({
      family_name: 'Myers', timezone: 'Europe/London', admin_display_name: 'Mom',
      admin_password: 'securepassword123', admin_pin: '2468',
    })
    expect(useAuthStore.getState().user?.role).toBe('admin')
  })

  it('checks the password and PIN before sending anything', async () => {
    const calls = mockApi({})
    const { container } = renderWizard()
    fillIn(container, { password: 'short' })
    fireEvent.submit(container.querySelector('form')!)
    expect(await screen.findByText('Password must be at least 8 characters')).toBeTruthy()
    fillIn(container, { pin: '12a' })
    fireEvent.submit(container.querySelector('form')!)
    expect(await screen.findByText('PIN must be 4-8 digits')).toBeTruthy()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('shows the server error, e.g. when setup already happened', async () => {
    mockApi({ 'POST /auth/setup': () => { throw apiError(400, 'Setup already completed') } })
    const { container } = renderWizard()
    fillIn(container)
    fireEvent.submit(container.querySelector('form')!)
    expect(await screen.findByText('Setup already completed')).toBeTruthy()
  })
})
