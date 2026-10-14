import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import FamilySettings from './FamilySettings'

const SETTINGS = { name: 'Myers', timezone: 'America/Detroit', sleep: { enabled: false, off: '22:00', on: '06:30' } }
const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement

describe('FamilySettings', () => {
  it('loads the current settings', async () => {
    mockApi({ 'GET /family': SETTINGS })
    renderApp(<FamilySettings />)
    await waitFor(() => expect(field('Family name').value).toBe('Myers'))
    expect((screen.getByLabelText('Timezone') as HTMLSelectElement).value).toBe('America/Detroit')
    expect(field('Turn wall screens off on a schedule').checked).toBe(false)
  })

  it('saves name, timezone and the sleep schedule', async () => {
    const calls = mockApi({ 'GET /family': SETTINGS, 'PATCH /family': (body: unknown) => ({ ...SETTINGS, ...(body as object) }) })
    renderApp(<FamilySettings />)
    await waitFor(() => expect(field('Family name').value).toBe('Myers'))
    fireEvent.change(field('Family name'), { target: { value: 'The Myers' } })
    fireEvent.change(screen.getByLabelText('Timezone'), { target: { value: 'Europe/London' } })
    fireEvent.click(field('Turn wall screens off on a schedule'))
    fireEvent.change(field('Screen off at'), { target: { value: '21:30' } })
    fireEvent.change(field('Screen on at'), { target: { value: '07:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Saved')).toBeTruthy()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
      name: 'The Myers', timezone: 'Europe/London', sleep: { enabled: true, off: '21:30', on: '07:00' },
    })
  })

  it('only offers the times when the schedule is on', async () => {
    mockApi({ 'GET /family': SETTINGS })
    renderApp(<FamilySettings />)
    await waitFor(() => expect(field('Family name').value).toBe('Myers'))
    expect(field('Screen off at').disabled).toBe(true)
    fireEvent.click(field('Turn wall screens off on a schedule'))
    expect(field('Screen off at').disabled).toBe(false)
  })

  it("shows the server's reason when saving fails", async () => {
    mockApi({ 'GET /family': SETTINGS, 'PATCH /family': () => { throw apiError(422, 'off and on times must differ') } })
    renderApp(<FamilySettings />)
    await waitFor(() => expect(field('Family name').value).toBe('Myers'))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/off and on times must differ|Could not save/)).toBeTruthy()
  })

  it('adds, names and removes extra wall clocks, up to three', async () => {
    const calls = mockApi({ 'GET /family': { ...SETTINGS, clocks: [{ label: 'Grandma', timezone: 'Europe/London' }] },
      'PATCH /family': (body: unknown) => ({ ...SETTINGS, ...(body as object) }) })
    renderApp(<FamilySettings />)
    await waitFor(() => expect(field('Clock 1 name').value).toBe('Grandma'))
    expect((screen.getByLabelText('Clock 1 timezone') as HTMLSelectElement).value).toBe('Europe/London')
    fireEvent.click(screen.getByRole('button', { name: 'Add a clock' }))
    fireEvent.change(field('Clock 2 name'), { target: { value: 'Tokyo office' } })
    fireEvent.change(screen.getByLabelText('Clock 2 timezone'), { target: { value: 'Asia/Tokyo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add a clock' }))
    expect((screen.getByRole('button', { name: 'Add a clock' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Remove clock 3' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Saved')).toBeTruthy()
    expect((calls.find((c) => c.method === 'PATCH')?.body as { clocks: unknown }).clocks).toEqual([
      { label: 'Grandma', timezone: 'Europe/London' }, { label: 'Tokyo office', timezone: 'Asia/Tokyo' },
    ])
  })
})
