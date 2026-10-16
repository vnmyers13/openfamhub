import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import VoiceAssistant from './VoiceAssistant'
import { mockApi } from '../test/api'
import { renderApp } from '../test/render'

describe('VoiceAssistant', () => {
  it('reviews an AI event draft and writes only after confirmation', async () => {
    const calls = mockApi({
      'POST /ai/draft': { action: { kind: 'event', operation: 'create', fields: {
        title: 'Soccer practice', start_dt: '2026-10-17T18:00:00+00:00', end_dt: '2026-10-17T19:00:00+00:00' } }, summary: 'Add Soccer practice.' },
      'POST /calendar/events': { id: 'event-1' },
    })
    renderApp(<VoiceAssistant />)

    fireEvent.click(screen.getByRole('button', { name: 'Ask local assistant' }))
    fireEvent.change(screen.getByLabelText('What would you like to do?'), { target: { value: 'Add soccer practice' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))

    expect(await screen.findByText('Add Soccer practice.')).toBeTruthy()
    expect(calls.some((c) => c.url === '/calendar/events')).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    await waitFor(() => expect(calls).toContainEqual(expect.objectContaining({ method: 'POST', url: '/calendar/events' })))
  })

  it('shows an unavailable local model without creating anything', async () => {
    mockApi({ 'POST /ai/draft': () => { throw Object.assign(new Error('off'), { response: { data: { detail: 'Local AI is unavailable.' } } }) } })
    renderApp(<VoiceAssistant />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask local assistant' }))
    fireEvent.change(screen.getByLabelText('What would you like to do?'), { target: { value: 'Add a task' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Local AI is unavailable.')
  })

  it('offers a WAV or MP3 voice recording as a local-model input', () => {
    mockApi({})
    renderApp(<VoiceAssistant />)
    fireEvent.click(screen.getByRole('button', { name: 'Ask local assistant' }))
    const input = screen.getByLabelText('Voice recording') as HTMLInputElement
    expect(input.accept).toBe('audio/wav,audio/mpeg')
  })
})
