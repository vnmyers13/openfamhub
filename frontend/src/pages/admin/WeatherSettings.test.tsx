import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import WeatherSettings from './WeatherSettings'

describe('WeatherSettings', () => {
  it('searches for a place and saves it with the chosen units', async () => {
    const calls = mockApi({
      'GET /weather/location': null,
      'GET /weather/places': [{ name: 'Ann Arbor, Michigan, United States', latitude: 42.28, longitude: -83.74 }],
      'PUT /weather/location': {},
    })
    renderApp(<WeatherSettings />)
    expect(await screen.findByText('No location yet.')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Find a place'), { target: { value: 'Ann Arbor' } })
    fireEvent.change(screen.getByLabelText('Units'), { target: { value: 'celsius' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Ann Arbor, Michigan, United States' }))
    expect(await screen.findByText('Weather is now for Ann Arbor, Michigan, United States')).toBeTruthy()
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual(
      { name: 'Ann Arbor, Michigan, United States', latitude: 42.28, longitude: -83.74, units: 'celsius' })
  })

  it('turns weather off, and explains failures', async () => {
    const calls = mockApi({
      'GET /weather/location': { name: 'Paris, France', latitude: 48.85, longitude: 2.35, units: 'celsius' },
      'DELETE /weather/location': null,
      'GET /weather/places': () => { throw apiError(502, "Couldn't search places right now") },
    })
    renderApp(<WeatherSettings />)
    expect(await screen.findByText('Paris, France')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Find a place'), { target: { value: 'Lyon' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText("Couldn't search places right now")).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Turn off' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
    expect(await screen.findByText('Weather turned off')).toBeTruthy()
  })
})
