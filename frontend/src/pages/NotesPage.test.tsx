import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { mockApi } from '../test/api'
import { renderApp } from '../test/render'
import NotesPage from './NotesPage'

const emptyBoard = { id: 'b1', title: 'Family notes', items: [], updated_by: null }
const signIn = (role: string) => useAuthStore.getState().setUser({ id: 'u1', display_name: 'Test', role, family_id: 'f' } as User)

describe('NotesPage', () => {
  it('lets a member add and save a note', async () => {
    signIn('member')
    const calls = mockApi({ 'GET /notes/board': emptyBoard, 'PUT /notes/board': emptyBoard })
    renderApp(<NotesPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add note' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save board' }))
    await waitFor(() => expect(calls.some((call) => call.method === 'PUT')).toBe(true))
  })

  it('keeps board editing controls hidden for viewers', async () => {
    signIn('viewer')
    mockApi({ 'GET /notes/board': emptyBoard })
    renderApp(<NotesPage />)
    await screen.findByRole('heading', { name: 'Family notes' })
    expect(screen.queryByRole('button', { name: 'Add note' })).toBeNull()
  })

  it('offers sticker, sketch, and local image export tools to members', async () => {
    signIn('member')
    mockApi({ 'GET /notes/board': emptyBoard })
    renderApp(<NotesPage />)
    await screen.findByLabelText('Board title')
    expect(screen.getByRole('button', { name: 'Add sticker' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Add sketch' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Export PNG' })).toBeTruthy()
  })
})
