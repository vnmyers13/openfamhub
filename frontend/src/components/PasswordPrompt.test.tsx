import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { requestPasswordPrompt } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import PasswordPrompt from './PasswordPrompt'

const open = () => {
  let promise!: Promise<void>
  act(() => {
    promise = requestPasswordPrompt()
  })
  return promise
}

describe('PasswordPrompt', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('stays hidden until an admin action asks for the password', () => {
    render(<PasswordPrompt />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('unlocks admin actions and resolves the waiting request', async () => {
    const calls = mockApi({ 'POST /auth/elevate': { id: 'mom', display_name: 'Mom', role: 'admin', admin_unlocked: true } })
    render(<PasswordPrompt />)
    const waiting = open()
    fireEvent.change(screen.getByRole('dialog').querySelector('input')!, { target: { value: 'securepassword123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Unlock' }))
    await expect(waiting).resolves.toBeUndefined()
    expect(calls.find((c) => c.url === '/auth/elevate')?.body).toEqual({ password: 'securepassword123' })
    expect(useAuthStore.getState().user?.admin_unlocked).toBe(true)
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('keeps the dialog open with the error when the password is wrong', async () => {
    mockApi({ 'POST /auth/elevate': () => { throw apiError(401, 'Incorrect password') } })
    render(<PasswordPrompt />)
    const waiting = open()
    waiting.catch(() => undefined)
    fireEvent.change(screen.getByRole('dialog').querySelector('input')!, { target: { value: 'nope-nope' } })
    fireEvent.click(screen.getByRole('button', { name: 'Unlock' }))
    expect(await screen.findByText('Incorrect password')).toBeTruthy()
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('rejects the waiting request when cancelled', async () => {
    render(<PasswordPrompt />)
    const waiting = open()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await expect(waiting).rejects.toBeDefined()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('cancels an open prompt when it unmounts, so later prompts still open', async () => {
    const first = render(<PasswordPrompt />)
    const waiting = open()
    first.unmount()
    await expect(waiting).rejects.toBeDefined()

    render(<PasswordPrompt />)
    const next = open()
    next.catch(() => undefined)
    expect(screen.getByRole('dialog')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  })
})
