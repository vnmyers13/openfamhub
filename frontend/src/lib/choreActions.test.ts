import { describe, expect, it } from 'vitest'
import type { ChoreInstance } from '../api/chores'
import { choreActions } from './choreActions'

const chore = (over: Partial<ChoreInstance>): ChoreInstance => ({
  id: 'c', template_id: 't', title: 'Dishes', points: 5, due_date: '2026-10-12', status: 'pending',
  assigned_to: null, claimed_by: null, completed_by: null, completed_at: null, routine_id: null, ...over,
})
const kid = { id: 'kid', role: 'member' }
const sib = { id: 'sib', role: 'member' }
const mom = { id: 'mom', role: 'admin' }
const grandma = { id: 'gm', role: 'viewer' }

describe('choreActions', () => {
  it('open chores can be claimed or done by anyone but viewers', () => {
    expect(choreActions(chore({}), kid)).toEqual(['claim', 'complete'])
    expect(choreActions(chore({}), grandma)).toEqual([])
    expect(choreActions(chore({}), null)).toEqual([])
  })

  it('assigned chores are for the assignee and admins only', () => {
    const c = chore({ assigned_to: 'kid' })
    expect(choreActions(c, kid)).toEqual(['complete'])
    expect(choreActions(c, sib)).toEqual([])
    expect(choreActions(c, mom)).toEqual(['complete'])
  })

  it('claimed chores can be done or given back by the claimer or an admin', () => {
    const c = chore({ status: 'claimed', claimed_by: 'kid' })
    expect(choreActions(c, kid)).toEqual(['complete', 'unclaim'])
    expect(choreActions(c, sib)).toEqual([])
    expect(choreActions(c, mom)).toEqual(['complete', 'unclaim'])
  })

  it('done chores can be undone by whoever did it, the assignee or an admin', () => {
    const c = chore({ status: 'completed', completed_by: 'kid' })
    expect(choreActions(c, kid)).toEqual(['undo'])
    expect(choreActions(c, sib)).toEqual([])
    expect(choreActions(c, mom)).toEqual(['undo'])
    expect(choreActions(chore({ status: 'completed', completed_by: 'mom', assigned_to: 'kid' }), kid)).toEqual(['undo'])
  })

  it('missed chores offer nothing', () => {
    expect(choreActions(chore({ status: 'missed', assigned_to: 'kid' }), mom)).toEqual([])
  })
})
