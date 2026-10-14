import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../../stores/auth'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import { MEMBERS, signIn } from '../chores/fixtures'
import BooksPage from './BooksPage'

const book = (id: string, title: string, over: object = {}) => ({
  id, title, author: null, notes: null, status: 'want_to_read', owner_id: 'kid', reader_id: null, finished_at: null,
  added_by: 'kid', points_awarded: false, ...over,
})

function booksApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /users/': MEMBERS,
    'GET /books': (params: unknown) => {
      const shelf = (params as { shelf: string }).shelf
      if (shelf === 'mine') return [book('b1', 'Holes', { status: 'reading', reader_id: 'kid', author: 'Louis Sachar' }), book('b2', 'Matilda')]
      if (shelf === 'family') return [book('l1', 'The Hobbit', { owner_id: null, added_by: 'mom' }),
        book('l2', 'Wonder', { owner_id: null, added_by: 'mom', status: 'reading', reader_id: 'mom' })]
      return [book('b1', 'Holes'), book('m1', "Mom's novel", { owner_id: 'mom', added_by: 'mom' })]
    },
    ...extra,
  })
}

const tab = (name: string) => fireEvent.click(screen.getByRole('tab', { name }))

describe('BooksPage', () => {
  afterEach(() => {
    useAuthStore.getState().clearUser()
    vi.restoreAllMocks()
  })

  it('adds to my list, starts and finishes a book, and cheers the points', async () => {
    const calls = booksApi({
      'POST /books': book('b3', 'Wonder'),
      'PATCH /books/b2': book('b2', 'Matilda', { status: 'reading' }),
      'PATCH /books/b1': book('b1', 'Holes', { status: 'finished', points_awarded: true }),
    })
    signIn('kid', 'member')
    renderApp(<BooksPage />)
    expect(await screen.findByText('Louis Sachar · Reading')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Book title'), { target: { value: 'Wonder' } })
    fireEvent.change(screen.getByLabelText('Author'), { target: { value: 'R. J. Palacio' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to my list' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: 'Start reading: Matilda' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'PATCH')).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: 'Finished it!: Holes' }))
    expect(await screen.findByText('🎉 Finished "Holes": +50 points!')).toBeTruthy()
    expect(calls.filter((c) => c.method !== 'GET').map((c) => [c.method, c.url, c.body])).toEqual([
      ['POST', '/books', { title: 'Wonder', author: 'R. J. Palacio', shelf: 'mine' }],
      ['PATCH', '/books/b2', { status: 'reading' }],
      ['PATCH', '/books/b1', { status: 'finished' }],
    ])
  })

  it('picks up a library book, and only admins or whoever added it can remove one', async () => {
    const calls = booksApi({ 'PATCH /books/l1': book('l1', 'The Hobbit', { owner_id: null, status: 'reading' }), 'POST /books': {} })
    signIn('kid', 'member')
    renderApp(<BooksPage />)
    tab('Family library')
    expect(await screen.findByText(/Reading · Mom/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Remove: The Hobbit' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Start reading: The Hobbit' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: 'Back on the shelf: Wonder' }))
    fireEvent.change(screen.getByLabelText('Book title'), { target: { value: 'Dune' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add to library' }))
    await waitFor(() => expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ title: 'Dune', author: null, shelf: 'family' }))
  })

  it("shows everyone's books with whose list they're on, and removes after confirming", async () => {
    const calls = booksApi({ 'DELETE /books/m1': null })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    signIn('mom', 'admin')
    renderApp(<BooksPage />)
    tab("Everyone's")
    expect(await screen.findByText(/Want to read · Kid's list/)).toBeTruthy()
    expect(screen.queryByLabelText('Book title')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: "Remove: Mom's novel" }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url === '/books/m1')).toBe(true))
  })

  it('viewers browse only, and errors are explained', async () => {
    booksApi()
    signIn('gm', 'viewer')
    const { unmount } = renderApp(<BooksPage />)
    expect(screen.queryByRole('tab', { name: 'My books' })).toBeNull()
    expect(await screen.findByText('Holes')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Start reading/ })).toBeNull()
    unmount()
    booksApi({ 'PATCH /books/b2': () => { throw apiError(403, "That's on someone else's list") } })
    signIn('kid', 'member')
    renderApp(<BooksPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Start reading: Matilda' }))
    expect(await screen.findByText("That's on someone else's list")).toBeTruthy()
  })
})
