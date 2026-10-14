import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { WallDashboardConfig } from '../../api/wall'
import WallDashboardEditor from './WallDashboardEditor'

const saved: WallDashboardConfig = {
  pages: [
    { name: 'Kitchen', duration_seconds: 45, widgets: [{ key: 'events', size: 'wide' }, { key: 'weather', size: 'normal' }] },
    { name: 'Family', duration_seconds: 30, widgets: [{ key: 'progress', size: 'wide' }] },
  ],
}

function renderEditor(config: WallDashboardConfig = saved) {
  const onChange = vi.fn()
  render(<WallDashboardEditor config={config} current={0} onSelect={vi.fn()} onChange={onChange} saving={false} />)
  return onChange
}

describe('WallDashboardEditor', () => {
  it('renders saved family wall pages and cards', () => {
    renderEditor()

    expect(screen.getByRole('heading', { name: 'Family wall dashboard' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Kitchen' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('tab', { name: 'Family' })).toBeTruthy()
    expect(screen.getByText("Today's events")).toBeTruthy()
    expect(screen.getByText('Weather')).toBeTruthy()
  })

  it('edits pages and cards by emitting the full updated config', () => {
    const onChange = renderEditor()

    fireEvent.change(screen.getByLabelText('Wall page name'), { target: { value: 'Main wall' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...saved, pages: [{ ...saved.pages[0], name: 'Main wall' }, saved.pages[1]] })

    fireEvent.change(screen.getByLabelText('Wall page duration'), { target: { value: '60' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...saved, pages: [{ ...saved.pages[0], duration_seconds: 60 }, saved.pages[1]] })

    fireEvent.click(screen.getByRole('button', { name: "Make wall card normal: Today's events" }))
    expect(onChange).toHaveBeenLastCalledWith({ ...saved, pages: [{ ...saved.pages[0], widgets: [{ key: 'events', size: 'normal' }, { key: 'weather', size: 'normal' }] }, saved.pages[1]] })

    fireEvent.click(screen.getByRole('button', { name: 'Move wall card down: Today\'s events' }))
    expect(onChange).toHaveBeenLastCalledWith({ ...saved, pages: [{ ...saved.pages[0], widgets: [{ key: 'weather', size: 'normal' }, { key: 'events', size: 'wide' }] }, saved.pages[1]] })

    fireEvent.click(screen.getByRole('button', { name: 'Remove wall card: Weather' }))
    expect(onChange).toHaveBeenLastCalledWith({ ...saved, pages: [{ ...saved.pages[0], widgets: [{ key: 'events', size: 'wide' }] }, saved.pages[1]] })
  })

  it('adds pages, adds cards, reset defaults, and prevents duplicate cards on a page', () => {
    const onChange = renderEditor()

    const addCard = screen.getByLabelText('Wall card to add')
    expect(within(addCard).queryByRole('option', { name: "Today's events" })).toBeNull()
    fireEvent.change(addCard, { target: { value: 'meals' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add wall card' }))
    expect(onChange).toHaveBeenLastCalledWith({ ...saved, pages: [{ ...saved.pages[0], widgets: [...saved.pages[0].widgets, { key: 'meals', size: 'normal' }] }, saved.pages[1]] })

    fireEvent.click(screen.getByRole('button', { name: 'Add wall page' }))
    expect(onChange).toHaveBeenLastCalledWith({ ...saved, pages: [...saved.pages, { name: 'Wall page', duration_seconds: 30, widgets: [] }] })

    fireEvent.click(screen.getByRole('button', { name: 'Delete wall page' }))
    expect(onChange).toHaveBeenLastCalledWith({ ...saved, pages: [saved.pages[1]] })

    fireEvent.click(screen.getByRole('button', { name: 'Reset wall dashboard' }))
    expect(onChange.mock.lastCall?.[0].pages.map((p: { name: string }) => p.name)).toEqual(['Today', 'Family', 'Notes'])
  })

  it('keeps an intentionally empty dashboard empty until a page is added', () => {
    const onChange = renderEditor({ pages: [] })

    expect(screen.getByText('No wall dashboard pages configured.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Add wall page' }))
    expect(onChange).toHaveBeenLastCalledWith({ pages: [{ name: 'Wall page', duration_seconds: 30, widgets: [] }] })
  })
})
