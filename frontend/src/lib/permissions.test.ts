import { describe, expect, it } from 'vitest'
import { canCreateEvents, canEditEvent } from './permissions'

const admin = { id: 'a', role: 'admin' }
const member = { id: 'm', role: 'member' }
const viewer = { id: 'v', role: 'viewer' }

describe('canCreateEvents (#13)', () => {
  it('lets admins and members add events', () => {
    expect(canCreateEvents(admin)).toBe(true)
    expect(canCreateEvents(member)).toBe(true)
  })

  it('keeps viewers and signed-out users read-only', () => {
    expect(canCreateEvents(viewer)).toBe(false)
    expect(canCreateEvents(null)).toBe(false)
  })
})

describe('canEditEvent', () => {
  const own = { createdBy: 'm', synced: false }
  const others = { createdBy: 'x', synced: false }
  const synced = { createdBy: null, synced: true }

  it('mirrors the API: admins edit any local event, members their own', () => {
    expect(canEditEvent(admin, others)).toBe(true)
    expect(canEditEvent(member, own)).toBe(true)
    expect(canEditEvent(member, others)).toBe(false)
  })

  it('never allows edits to subscribed-calendar events or by viewers', () => {
    expect(canEditEvent(admin, synced)).toBe(false)
    expect(canEditEvent(viewer, { createdBy: 'v', synced: false })).toBe(false)
    expect(canEditEvent(null, own)).toBe(false)
  })
})
