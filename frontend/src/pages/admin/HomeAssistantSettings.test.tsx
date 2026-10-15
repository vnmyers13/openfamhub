import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import HomeAssistantSettings from './HomeAssistantSettings'

const ENTITIES = [
  { entity_id: 'light.kitchen', name: 'Kitchen light', domain: 'light', state: 'on' },
  { entity_id: 'light.porch', name: 'Porch light', domain: 'light', state: 'off' },
  { entity_id: 'script.good_morning', name: 'Good morning', domain: 'script', state: 'off' },
  { entity_id: 'sensor.outside', name: 'Outside', domain: 'sensor', state: '12' },
]
const ROUTINES = [
  { id: 'r1', name: 'Morning', assigned_to: null, start_time: '07:00', repeat: null, start_date: '2026-10-01', steps: [] },
  { id: 'r2', name: 'Anytime', assigned_to: null, start_time: null, repeat: null, start_date: '2026-10-01', steps: [] },
]

describe('Admin › Settings › Home Assistant', () => {
  it('explains how to connect it when the server has no URL or token', async () => {
    mockApi({ 'GET /ha/status': { configured: false, reachable: false, error: null }, 'GET /ha/config': { entities: [], routine_scenes: {} } })
    renderApp(<HomeAssistantSettings />)
    expect(await screen.findByText(/Not set up/)).toBeTruthy()
    expect(screen.getByText('HA_TOKEN')).toBeTruthy()
  })

  it("shows why it can't connect", async () => {
    mockApi({ 'GET /ha/status': { configured: true, reachable: false, error: 'Home Assistant refused the access token (check HA_TOKEN).' },
      'GET /ha/config': { entities: [], routine_scenes: {} } })
    renderApp(<HomeAssistantSettings />)
    expect((await screen.findByRole('alert')).textContent).toMatch(/refused the access token/)
  })

  it('chooses entities in order and a scene for a timed routine', async () => {
    const calls = mockApi({
      'GET /ha/status': { configured: true, reachable: true, error: null },
      'GET /ha/config': { entities: ['sensor.outside'], routine_scenes: {} },
      'GET /ha/entities': ENTITIES,
      'GET /routines': ROUTINES,
      'PUT /ha/config': (body: unknown) => body,
    })
    renderApp(<HomeAssistantSettings />)
    expect(await screen.findByText('Connected.')).toBeTruthy()
    fireEvent.change(await screen.findByLabelText('Find an entity'), { target: { value: 'light' } })
    expect(screen.queryByText('Outside')).toBeNull()
    fireEvent.click(screen.getByLabelText(/Porch light/))
    fireEvent.click(screen.getByLabelText(/Kitchen light/))
    fireEvent.change(await screen.findByLabelText('Scene for Morning'), { target: { value: 'script.good_morning' } })
    expect(screen.queryByLabelText('Scene for Anytime')).toBeNull()  // no start time, nothing to start
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Saved.')).toBeTruthy()
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({
      entities: ['sensor.outside', 'light.porch', 'light.kitchen'], routine_scenes: { r1: 'script.good_morning' } })
  })

  it('unticks an entity and explains a failed save', async () => {
    const calls = mockApi({
      'GET /ha/status': { configured: true, reachable: true, error: null },
      'GET /ha/config': { entities: ['light.kitchen', 'sensor.outside'], routine_scenes: { r1: 'script.good_morning' } },
      'GET /ha/entities': ENTITIES,
      'GET /routines': ROUTINES,
      'PUT /ha/config': () => { throw apiError(400, "That routine isn't one of this family's") },
    })
    renderApp(<HomeAssistantSettings />)
    fireEvent.click(await screen.findByLabelText(/Kitchen light/))
    fireEvent.change(await screen.findByLabelText('Scene for Morning'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect((await screen.findByRole('alert')).textContent).toBe("That routine isn't one of this family's")
    await waitFor(() => expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ entities: ['sensor.outside'], routine_scenes: {} }))
  })
})
