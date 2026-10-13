import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import Login from './Login'

const MOM = { id: 'mom', display_name: 'Mom', color_hex: '#4F46E5', avatar_type: 'emoji', avatar_value: '🦊', has_pin: true }
const KID = { id: 'kid', display_name: 'Kid', color_hex: '#059669', avatar_type: null, avatar_value: null, has_pin: true }
const GRANDPA = { id: 'gp', display_name: 'Grandpa', color_hex: '#DC2626', avatar_type: null, avatar_value: null, has_pin: false }
const USER = { id: 'kid', display_name: 'Kid', role: 'member', family_id: 'f' }

const renderLogin = () => renderApp(<Login />, { path: '/login', routes: { '/dashboard': 'dashboard page' } })
const tap = (label: string) => fireEvent.click(screen.getByRole('button', { name: label }))

describe('Login', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('offers only members who have a PIN', async () => {
    mockApi({ 'GET /auth/profiles': [MOM, KID, GRANDPA] })
    renderLogin()
    expect(await screen.findByText("Who's here?")).toBeTruthy()
    expect(screen.getByRole('button', { name: /Mom/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Kid/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Grandpa/ })).toBeNull()
  })

  it('signs in with the PIN pad and goes to the dashboard', async () => {
    const calls = mockApi({ 'GET /auth/profiles': [MOM, KID], 'POST /auth/login/pin': USER })
    renderLogin()
    fireEvent.click(await screen.findByRole('button', { name: /Kid/ }))
    expect(screen.getByText('Hi Kid! Enter your PIN')).toBeTruthy()
    for (const d of ['1', '3', '5', '7']) tap(d)
    expect(screen.getByLabelText('4 digits entered')).toBeTruthy()
    tap('Sign in')
    expect(await screen.findByText('dashboard page')).toBeTruthy()
    expect(calls.find((c) => c.url === '/auth/login/pin')?.body).toEqual({ user_id: 'kid', pin: '1357' })
    expect(useAuthStore.getState().user?.id).toBe('kid')
  })

  it('needs at least four digits and supports delete', async () => {
    mockApi({ 'GET /auth/profiles': [KID] })
    renderLogin()
    fireEvent.click(await screen.findByRole('button', { name: /Kid/ }))
    for (const d of ['1', '2', '3']) tap(d)
    expect((screen.getByRole('button', { name: 'Sign in' }) as HTMLButtonElement).disabled).toBe(true)
    tap('Delete')
    expect(screen.getByLabelText('2 digits entered')).toBeTruthy()
  })

  it('shows the server message and clears the PIN when it is wrong', async () => {
    mockApi({
      'GET /auth/profiles': [KID],
      'POST /auth/login/pin': () => { throw apiError(401, 'Invalid PIN') },
    })
    renderLogin()
    fireEvent.click(await screen.findByRole('button', { name: /Kid/ }))
    for (const d of ['9', '9', '9', '9']) tap(d)
    tap('Sign in')
    expect(await screen.findByText('Invalid PIN')).toBeTruthy()
    expect(screen.getByLabelText('0 digits entered')).toBeTruthy()
  })

  it('accepts digits and Enter from a keyboard, and Escape goes back', async () => {
    const calls = mockApi({ 'GET /auth/profiles': [KID], 'POST /auth/login/pin': USER })
    renderLogin()
    fireEvent.click(await screen.findByRole('button', { name: /Kid/ }))
    for (const key of ['2', '4', '6', '8', 'Backspace', '8']) fireEvent.keyDown(window, { key })
    fireEvent.keyDown(window, { key: 'Enter' })
    await waitFor(() => expect(calls.some((c) => c.url === '/auth/login/pin')).toBe(true))
    expect(calls.find((c) => c.url === '/auth/login/pin')?.body).toEqual({ user_id: 'kid', pin: '2468' })
  })

  it('goes straight to the password form when nobody has a PIN', async () => {
    const calls = mockApi({ 'GET /auth/profiles': [GRANDPA], 'POST /auth/login': USER })
    renderLogin()
    expect(await screen.findByText('Sign in with your password')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Grandpa' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'longpassword' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText('dashboard page')).toBeTruthy()
    expect(calls.find((c) => c.url === '/auth/login')?.body).toEqual({ display_name: 'Grandpa', password: 'longpassword' })
  })

  it('shows password errors from the server', async () => {
    mockApi({
      'GET /auth/profiles': [],
      'POST /auth/login': () => { throw apiError(429, 'Too many attempts. Try again in 1 minute.') },
    })
    renderLogin()
    fireEvent.change(await screen.findByLabelText('Name'), { target: { value: 'Mom' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrongpassword' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign In' }))
    expect(await screen.findByText('Too many attempts. Try again in 1 minute.')).toBeTruthy()
  })

  it('"Use password" from the PIN pad fills in the name', async () => {
    mockApi({ 'GET /auth/profiles': [MOM] })
    renderLogin()
    fireEvent.click(await screen.findByRole('button', { name: /Mom/ }))
    tap('Use password')
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Mom')
    tap('← Back to the family picker')
    expect(screen.getByText("Who's here?")).toBeTruthy()
  })
})
