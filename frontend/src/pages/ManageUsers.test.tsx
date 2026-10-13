import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import ManageUsers from './ManageUsers'

const MOM = { id: 'mom', display_name: 'Mom', role: 'admin', color_hex: '#4F46E5', ui_mode: 'standard',
  avatar_type: 'emoji', avatar_value: '🦊', family_id: 'f', has_pin: true }
const KID = { ...MOM, id: 'kid', display_name: 'Kid', role: 'member', avatar_value: '🐢' }

function signIn(role = 'admin') {
  useAuthStore.getState().setUser({ ...MOM, role } as User)
}

const field = (label: RegExp) => screen.getByLabelText(label) as HTMLInputElement

describe('ManageUsers', () => {
  afterEach(() => {
    useAuthStore.getState().clearUser()
    vi.unstubAllGlobals()
  })

  it('is admin-only', () => {
    signIn('member')
    mockApi({ 'GET /users/': [] })
    renderApp(<ManageUsers />)
    expect(screen.getByText('Access denied')).toBeTruthy()
  })

  it('lists the family', async () => {
    signIn()
    mockApi({ 'GET /users/': [MOM, KID] })
    renderApp(<ManageUsers />)
    expect(await screen.findByText('Kid')).toBeTruthy()
    expect(screen.getAllByText('Mom').length).toBeGreaterThan(0)
  })

  it('adds a member with a PIN', async () => {
    signIn()
    const calls = mockApi({ 'GET /users/': [MOM], 'POST /users/': KID })
    renderApp(<ManageUsers />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add member' }))
    fireEvent.change(field(/^Name/), { target: { value: 'Kid' } })
    fireEvent.change(field(/PIN/), { target: { value: '1357' } })
    fireEvent.click(screen.getByRole('button', { name: 'Avatar 🐢' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      display_name: 'Kid', role: 'member', pin: '1357', avatar: '🐢', password: undefined,
    })
  })

  it('checks the form before saving', async () => {
    signIn()
    const calls = mockApi({ 'GET /users/': [MOM] })
    renderApp(<ManageUsers />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add member' }))
    fireEvent.change(field(/^Name/), { target: { value: 'Kid' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Give them a PIN, a password, or both')).toBeTruthy()

    fireEvent.change(field(/PIN/), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('PIN must be 4-8 digits')).toBeTruthy()

    fireEvent.change(field(/PIN/), { target: { value: '1234' } })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'admin' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Admins need a password for admin changes')).toBeTruthy()

    fireEvent.change(field(/Password/), { target: { value: 'short' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Password must be at least 8 characters')).toBeTruthy()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it("shows the server's reason, e.g. a duplicate name", async () => {
    signIn()
    mockApi({ 'GET /users/': [MOM], 'POST /users/': () => { throw apiError(409, 'Someone in the family is already called "Mom"') } })
    renderApp(<ManageUsers />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add member' }))
    fireEvent.change(field(/^Name/), { target: { value: 'mom' } })
    fireEvent.change(field(/PIN/), { target: { value: '1357' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Someone in the family is already called "Mom"')).toBeTruthy()
  })

  it('edits a member without resending blank credentials', async () => {
    signIn()
    const calls = mockApi({ 'GET /users/': [MOM, KID], 'PATCH /users/kid': KID })
    renderApp(<ManageUsers />)
    await screen.findByText('Kid')
    fireEvent.click(screen.getAllByRole('button', { name: 'Edit' })[1])
    expect(screen.getByText('Edit Kid')).toBeTruthy()
    fireEvent.change(field(/^Name/), { target: { value: 'Sam' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(calls.find((c) => c.method === 'PATCH')?.body).toMatchObject({ display_name: 'Sam', pin: undefined, password: undefined })
  })

  it('removes a member after confirming', async () => {
    signIn()
    const calls = mockApi({ 'GET /users/': [MOM, KID], 'DELETE /users/kid': null })
    vi.stubGlobal('confirm', vi.fn(() => true))
    renderApp(<ManageUsers />)
    await screen.findByText('Kid')
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url === '/users/kid')).toBe(true))
  })
})
