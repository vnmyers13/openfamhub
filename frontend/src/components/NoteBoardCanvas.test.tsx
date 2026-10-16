import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import NoteBoardCanvas, { type NoteBoard } from './NoteBoardCanvas'

const board: NoteBoard = { id: 'board-1', title: 'Family notes', updated_by: null, items: [
  { id: 'note-1', type: 'note', x: 10, y: 10, width: 200, height: 100, color: '#fef08a', text: 'Pack lunches' },
  { id: 'sticker-1', type: 'sticker', x: 300, y: 10, size: 60, emoji: '⭐' },
  { id: 'image-1', type: 'image', x: 10, y: 200, width: 200, height: 100, media_id: 'photo-1' },
  { id: 'stroke-1', type: 'stroke', color: '#000000', points: [{ x: 1, y: 1 }, { x: 20, y: 20 }] },
] }

describe('NoteBoardCanvas', () => {
  it('renders note, sticker, image, and freehand stroke items', () => {
    render(<NoteBoardCanvas board={board} imageUrl={(id) => `/media/${id}`} readOnly />)

    expect(screen.getByText('Pack lunches')).toBeTruthy()
    expect(screen.getByLabelText('Sticker: ⭐')).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Board photo' }).getAttribute('href')).toBe('/media/photo-1')
    expect(document.querySelector('polyline')).toBeTruthy()
  })
})
