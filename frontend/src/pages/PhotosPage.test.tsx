import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import PhotosPage from './PhotosPage'

function signIn(role: string, id = 'u1') {
  useAuthStore.getState().setUser({ id, display_name: 'Test', role, family_id: 'f' } as User)
}

const item = (id: string, over: object = {}) => ({
  id, kind: 'photo', status: 'ready', error: null, original_name: `${id}.jpg`, width: 1920, height: 1280,
  duration_s: null, uploaded_by: 'u1', created_at: '2026-10-12T10:00:00+00:00',
  wall_url: `/api/media/${id}/wall`, thumb_url: `/api/media/${id}/thumb`, ...over,
})

const file = (name: string, type: string) => new File(['x'], name, { type })
const choose = (files: File[]) =>
  fireEvent.change(screen.getByLabelText('Add photos or videos'), { target: { files } })

describe('PhotosPage', () => {
  afterEach(() => {
    useAuthStore.getState().clearUser()
    vi.unstubAllGlobals()
  })

  it('shows the library with thumbnails and states', async () => {
    signIn('member')
    mockApi({ 'GET /media': [
      item('beach'),
      item('clip', { kind: 'video', duration_s: 75, original_name: 'clip.mp4' }),
      item('new', { status: 'processing', original_name: 'new.mov', kind: 'video' }),
      item('bad', { status: 'failed', error: 'ffmpeg exited with code 1', original_name: 'bad.mov' }),
    ] })
    renderApp(<PhotosPage />)
    expect(((await screen.findByAltText('beach.jpg')) as HTMLImageElement).getAttribute('src')).toBe('/api/media/beach/thumb')
    expect(screen.getByText('1:15')).toBeTruthy()
    expect(screen.getByText('Converting…')).toBeTruthy()
    expect(screen.getByText(/ffmpeg exited with code 1/)).toBeTruthy()
  })

  it('says when the library is empty', async () => {
    signIn('member')
    mockApi({ 'GET /media': [] })
    renderApp(<PhotosPage />)
    expect(await screen.findByText(/No photos or videos yet/)).toBeTruthy()
  })

  it('uploads each chosen file as the raw body, one at a time', async () => {
    signIn('member')
    const calls = mockApi({ 'GET /media': [], 'POST /media': (body: unknown) => item((body as File).name) })
    renderApp(<PhotosPage />)
    await screen.findByText(/No photos or videos yet/)
    const files = [file('a.jpg', 'image/jpeg'), file('b.mp4', 'video/mp4')]
    choose(files)
    await waitFor(() => expect(calls.filter((c) => c.method === 'POST')).toHaveLength(2))
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.body)).toEqual(files)
  })

  it("lists each file that couldn't be added, with the reason", async () => {
    signIn('member')
    mockApi({
      'GET /media': [],
      'POST /media': (body: unknown) => {
        if ((body as File).name.endsWith('.heic')) throw apiError(415, "HEIC/HEIF photos aren't supported yet.")
        return item('ok')
      },
    })
    renderApp(<PhotosPage />)
    await screen.findByText(/No photos or videos yet/)
    choose([file('IMG_1.heic', 'image/heic'), file('ok.jpg', 'image/jpeg')])
    expect(await screen.findByText(/IMG_1\.heic: HEIC\/HEIF photos aren't supported yet\./)).toBeTruthy()
  })

  it('hides uploading and removing from viewers', async () => {
    signIn('viewer', 'grandma')
    mockApi({ 'GET /media': [item('beach')] })
    renderApp(<PhotosPage />)
    await screen.findByAltText('beach.jpg')
    expect(screen.queryByLabelText('Add photos or videos')).toBeNull()
    expect(screen.queryByRole('button', { name: /Remove/ })).toBeNull()
  })

  it('lets uploaders and admins remove items after confirming', async () => {
    signIn('member', 'u1')
    const calls = mockApi({
      'GET /media': [item('mine'), item('theirs', { uploaded_by: 'someone-else' })],
      'DELETE /media/mine': null,
    })
    vi.stubGlobal('confirm', vi.fn(() => true))
    renderApp(<PhotosPage />)
    await screen.findByAltText('mine.jpg')
    expect(screen.queryByRole('button', { name: 'Remove theirs.jpg' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Remove mine.jpg' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
  })

  it('admins can remove anyone’s items', async () => {
    signIn('admin', 'boss')
    mockApi({ 'GET /media': [item('theirs', { uploaded_by: 'kid' })] })
    renderApp(<PhotosPage />)
    const card = (await screen.findByAltText('theirs.jpg')).closest('li') as HTMLElement
    expect(within(card).getByRole('button', { name: 'Remove theirs.jpg' })).toBeTruthy()
  })
})
