import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '../../stores/auth'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import { MEMBERS, signIn } from '../chores/fixtures'
import RewardsPage from './RewardsPage'

const tab = (name: string) => fireEvent.click(screen.getByRole('tab', { name }))

const reward = (id: string, name: string, cost: number, over: object = {}) => ({
  id, name, description: null, icon: '🎁', point_cost: cost, needs_approval: false, is_active: true, ...over,
})
const progress = (id: string, name: string, points: number, badges: object[] = []) => ({
  user_id: id, display_name: name, color_hex: '#059669', avatar_value: null, points_balance: points,
  points_this_week: 0, streak_days: 0, badges,
})
const request = (id: string, user: string, name: string, status = 'pending', over: object = {}) => ({
  id, reward_id: `r-${id}`, user_id: user, reward_name: name, point_cost: 30, status, note: null,
  requested_at: '2026-10-13T12:00:00+00:00', decided_at: null, decided_by: null, ...over,
})
const badge = (id: string, name: string, over: object = {}) => ({
  id, name, description: null, icon: '🏅', kind: 'chores_completed', threshold: 10, bonus_points: 0, is_active: true, ...over,
})

function rewardsApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /users/': MEMBERS,
    'GET /rewards/catalog': [reward('r1', 'Movie pick', 30), reward('r2', 'Zoo trip', 200, { needs_approval: true }),
      reward('r3', 'Stay up late', 40, { needs_approval: true })],
    'GET /rewards/progress': [progress('mom', 'Mom', 0), progress('kid', 'Kid', 50, [{ id: 'b1', name: 'Helper', icon: '🏅' }])],
    'GET /rewards/points/history': [
      { id: 'h1', delta: 5, reason: 'Chore: Feed the cat', source_type: 'chore', created_at: '2026-10-13T12:00:00+00:00' },
      { id: 'h2', delta: -30, reason: 'Reward: Movie pick', source_type: 'reward', created_at: '2026-10-12T12:00:00+00:00' }],
    'GET /rewards/redemptions': [],
    'GET /rewards/badges': [badge('b1', 'Helper'), badge('b2', 'On a roll', { kind: 'streak_days', threshold: 7, bonus_points: 20 })],
    'GET /rewards/allowance': [{ user_id: 'kid', display_name: 'Kid', weekly_cents: 500, balance_cents: 1250, next_payout: '2026-10-19' }],
    'GET /rewards/allowance/kid/history': [{ id: 'a1', delta_cents: 500, reason: 'Weekly allowance', source_type: 'weekly',
      week_start: '2026-10-12', created_at: '2026-10-12T11:00:00+00:00' }],
    ...extra,
  })
}

describe('RewardsPage', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('shows Manage to admins only', () => {
    rewardsApi()
    signIn('kid', 'member')
    const { unmount } = renderApp(<RewardsPage />)
    expect(screen.queryByRole('tab', { name: 'Manage' })).toBeNull()
    unmount()
    signIn('mom', 'admin')
    renderApp(<RewardsPage />)
    expect(screen.getByRole('tab', { name: 'Manage' })).toBeTruthy()
  })

  describe('Rewards', () => {
    it('shows my points and what I can afford', async () => {
      rewardsApi()
      signIn('kid', 'member')
      renderApp(<RewardsPage />)
      expect(await screen.findByText('⭐ 50')).toBeTruthy()
      expect(await screen.findByText('Chore: Feed the cat')).toBeTruthy()
      await waitFor(() => expect((screen.getByRole('button', { name: 'Get: Movie pick' }) as HTMLButtonElement).disabled).toBe(false))
      expect((screen.getByRole('button', { name: 'Ask for: Zoo trip' }) as HTMLButtonElement).disabled).toBe(true)
      expect(screen.getByText('150 more to go')).toBeTruthy()
    })

    it('buys a reward and asks for one that needs a yes', async () => {
      const calls = rewardsApi({
        'POST /rewards/catalog/r1/redeem': request('x', 'kid', 'Movie pick', 'approved'),
        'POST /rewards/catalog/r3/redeem': request('y', 'kid', 'Stay up late'),
      })
      signIn('kid', 'member')
      renderApp(<RewardsPage />)
      await screen.findByText('⭐ 50')
      fireEvent.click(await screen.findByRole('button', { name: 'Get: Movie pick' }))
      expect(await screen.findByText('Movie pick is yours!')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Ask for: Stay up late' }))
      expect(await screen.findByText(/Asked for Stay up late/)).toBeTruthy()
      expect(calls.filter((c) => c.method === 'POST').map((c) => c.url)).toEqual(
        ['/rewards/catalog/r1/redeem', '/rewards/catalog/r3/redeem'])
    })

    it("shows the server's reason when buying fails", async () => {
      rewardsApi({ 'POST /rewards/catalog/r1/redeem': () => { throw apiError(409, 'Not enough points: you have 10, this costs 30') } })
      signIn('kid', 'member')
      renderApp(<RewardsPage />)
      await screen.findByText('⭐ 50')
      fireEvent.click(await screen.findByRole('button', { name: 'Get: Movie pick' }))
      expect(await screen.findByText('Not enough points: you have 10, this costs 30')).toBeTruthy()
    })

    it('viewers can look but not spend', async () => {
      rewardsApi()
      signIn('gm', 'viewer')
      renderApp(<RewardsPage />)
      expect(await screen.findByText('Movie pick')).toBeTruthy()
      expect(screen.queryByRole('button', { name: /Get:|Ask for:/ })).toBeNull()
      expect(screen.queryByText('My points')).toBeNull()
    })
  })

  describe('Requests', () => {
    it('admins say yes or no, with a reason', async () => {
      const calls = rewardsApi({
        'GET /rewards/redemptions': [request('q1', 'kid', 'Zoo trip'), request('q2', 'kid', 'Stay up late'),
          request('q3', 'kid', 'Movie pick', 'approved')],
        'POST /rewards/redemptions/q1/approve': request('q1', 'kid', 'Zoo trip', 'approved'),
        'POST /rewards/redemptions/q2/reject': request('q2', 'kid', 'Stay up late', 'rejected'),
      })
      signIn('mom', 'admin')
      renderApp(<RewardsPage />)
      tab('Requests')
      fireEvent.click(await screen.findByRole('button', { name: 'Approve: Zoo trip' }))
      await waitFor(() => expect((screen.getByRole('button', { name: 'Reject: Stay up late' }) as HTMLButtonElement).disabled).toBe(false))
      fireEvent.click(screen.getByRole('button', { name: 'Reject: Stay up late' }))
      fireEvent.change(screen.getByLabelText('Reason (optional)'), { target: { value: 'School night' } })
      fireEvent.click(screen.getByRole('button', { name: 'Say no' }))
      await waitFor(() => expect(calls.filter((c) => c.method === 'POST')).toEqual([
        { method: 'POST', url: '/rewards/redemptions/q1/approve', body: undefined },
        { method: 'POST', url: '/rewards/redemptions/q2/reject', body: { note: 'School night' } },
      ]))
      expect(screen.getByText(/Movie pick — Kid/)).toBeTruthy()
    })

    it('members see their own requests and can cancel a waiting one', async () => {
      const calls = rewardsApi({
        'GET /rewards/redemptions': [request('q1', 'kid', 'Zoo trip'), request('q2', 'kid', 'Movie pick', 'rejected', { note: 'Not today' })],
        'POST /rewards/redemptions/q1/cancel': request('q1', 'kid', 'Zoo trip', 'cancelled'),
      })
      signIn('kid', 'member')
      renderApp(<RewardsPage />)
      tab('Requests')
      expect(await screen.findByText('My requests')).toBeTruthy()
      expect(screen.queryByText('Waiting for you')).toBeNull()
      expect(await screen.findByText(/Not today/)).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Cancel: Zoo trip' }))
      await waitFor(() => expect(calls.some((c) => c.url === '/rewards/redemptions/q1/cancel')).toBe(true))
      expect(screen.queryByRole('button', { name: 'Cancel: Movie pick' })).toBeNull()
    })

    it("shows the server's reason when a decision fails", async () => {
      rewardsApi({
        'GET /rewards/redemptions': [request('q1', 'kid', 'Zoo trip')],
        'POST /rewards/redemptions/q1/approve': () => { throw apiError(409, 'This request was already decided') },
      })
      signIn('mom', 'admin')
      renderApp(<RewardsPage />)
      tab('Requests')
      fireEvent.click(await screen.findByRole('button', { name: 'Approve: Zoo trip' }))
      expect(await screen.findByText('This request was already decided')).toBeTruthy()
    })
  })

  it('Badges shows how to earn each one and which I have', async () => {
    rewardsApi()
    signIn('kid', 'member')
    renderApp(<RewardsPage />)
    tab('Badges')
    expect(await screen.findByText('Complete 10 chores')).toBeTruthy()
    expect(screen.getByText('A 7-day streak · +20 bonus')).toBeTruthy()
    await waitFor(() => expect(screen.getAllByText('Earned')).toHaveLength(1))
  })

  describe('Allowance', () => {
    it('members see their balance, next payout and history', async () => {
      rewardsApi()
      signIn('kid', 'member')
      renderApp(<RewardsPage />)
      tab('Allowance')
      expect(await screen.findByText('$12.50')).toBeTruthy()
      expect(screen.getByText(/\$5\.00 every Monday · next Oct 19/)).toBeTruthy()
      expect(await screen.findByText('Weekly allowance')).toBeTruthy()
    })

    it('admins set the weekly amount and record payouts', async () => {
      const calls = rewardsApi({
        'PUT /rewards/allowance/kid': { user_id: 'kid', display_name: 'Kid', weekly_cents: 750, balance_cents: 1250, next_payout: '2026-10-19' },
        'POST /rewards/allowance/kid/adjust': { id: 'a2' },
      })
      signIn('mom', 'admin')
      renderApp(<RewardsPage />)
      tab('Allowance')
      expect(await screen.findByLabelText('Kid balance')).toBeTruthy()
      fireEvent.change(screen.getByLabelText('Weekly allowance for Kid'), { target: { value: '7.50' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save weekly allowance for Kid' }))
      fireEvent.change(screen.getByLabelText('Amount paid to Kid'), { target: { value: '10' } })
      fireEvent.click(screen.getByRole('button', { name: 'Record payout to Kid' }))
      await waitFor(() => expect(calls.filter((c) => c.method !== 'GET')).toEqual([
        { method: 'PUT', url: '/rewards/allowance/kid', body: { weekly_cents: 750 } },
        { method: 'POST', url: '/rewards/allowance/kid/adjust', body: { delta_cents: -1000, reason: 'Paid out' } },
      ]))
      fireEvent.click(screen.getByRole('button', { name: 'History' }))
      expect(await screen.findByText('Weekly allowance')).toBeTruthy()
    })

    it("refuses an amount that isn't money", async () => {
      const calls = rewardsApi()
      signIn('mom', 'admin')
      renderApp(<RewardsPage />)
      tab('Allowance')
      fireEvent.change(await screen.findByLabelText('Weekly allowance for Kid'), { target: { value: 'lots' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save weekly allowance for Kid' }))
      expect(await screen.findByText('Enter an amount like 5 or 5.50')).toBeTruthy()
      expect(calls.filter((c) => c.method === 'PUT')).toEqual([])
    })
  })

  describe('Manage', () => {
    it('adds, edits and retires rewards', async () => {
      const calls = rewardsApi({
        'GET /rewards/catalog': (params: unknown) => (params as { include_inactive?: boolean } | undefined)?.include_inactive
          ? [reward('r1', 'Movie pick', 30), reward('r9', 'Old prize', 10, { is_active: false })] : [],
        'POST /rewards/catalog': reward('r4', 'Ice cream', 25),
        'PATCH /rewards/catalog/r1': reward('r1', 'Movie pick', 35),
        'PATCH /rewards/catalog/r9': reward('r9', 'Old prize', 10),
        'DELETE /rewards/catalog/r1': null,
      })
      signIn('mom', 'admin')
      renderApp(<RewardsPage />)
      tab('Manage')
      fireEvent.click(screen.getByRole('button', { name: '+ Reward' }))
      fireEvent.change(screen.getByLabelText('Reward'), { target: { value: 'Ice cream' } })
      fireEvent.change(screen.getByLabelText('Points'), { target: { value: '25' } })
      fireEvent.click(screen.getByLabelText(/Needs a grown-up's yes/))
      fireEvent.click(screen.getByRole('button', { name: 'Save reward' }))
      await waitFor(() => expect(calls.find((c) => c.method === 'POST')?.body).toEqual(
        { id: undefined, name: 'Ice cream', icon: '🎁', point_cost: 25, needs_approval: true, description: null }))
      fireEvent.click(await screen.findByRole('button', { name: 'Edit: Movie pick' }))
      fireEvent.change(screen.getByLabelText('Points'), { target: { value: '35' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save reward' }))
      fireEvent.click(await screen.findByRole('button', { name: 'Retire: Movie pick' }))
      fireEvent.click(screen.getByRole('button', { name: 'Bring back: Old prize' }))
      await waitFor(() => expect(calls.filter((c) => c.method === 'PATCH' || c.method === 'DELETE').map((c) => [c.method, c.url, c.body])).toEqual([
        ['PATCH', '/rewards/catalog/r1', { name: 'Movie pick', icon: '🎁', point_cost: 35, needs_approval: false, description: null }],
        ['DELETE', '/rewards/catalog/r1', undefined],
        ['PATCH', '/rewards/catalog/r9', { is_active: true }],
      ]))
    })

    it('adds and retires badges', async () => {
      const calls = rewardsApi({
        'POST /rewards/badges': badge('b3', 'Week warrior'),
        'DELETE /rewards/badges/b1': null,
      })
      signIn('mom', 'admin')
      renderApp(<RewardsPage />)
      tab('Manage')
      fireEvent.click(screen.getByRole('button', { name: '+ Badge' }))
      fireEvent.change(screen.getByLabelText('Badge'), { target: { value: 'Week warrior' } })
      fireEvent.change(screen.getByLabelText('Earned by'), { target: { value: 'streak_days' } })
      fireEvent.change(screen.getByLabelText('Reach'), { target: { value: '7' } })
      fireEvent.change(screen.getByLabelText('Bonus pts'), { target: { value: '15' } })
      expect(screen.getByText(/A 7-day streak\. Anyone who already qualifies/)).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Save badge' }))
      fireEvent.click(await screen.findByRole('button', { name: 'Retire: Helper' }))
      await waitFor(() => expect(calls.filter((c) => c.method !== 'GET').map((c) => [c.method, c.url, c.body])).toEqual([
        ['POST', '/rewards/badges', { id: undefined, name: 'Week warrior', icon: '🏅', kind: 'streak_days', threshold: 7, bonus_points: 15 }],
        ['DELETE', '/rewards/badges/b1', undefined],
      ]))
    })

    it('gives or takes points with a reason', async () => {
      const calls = rewardsApi({ 'POST /rewards/points/adjust': { id: 'p1' } })
      signIn('mom', 'admin')
      renderApp(<RewardsPage />)
      tab('Manage')
      await screen.findByRole('option', { name: 'Kid' })
      fireEvent.change(screen.getByLabelText('Who'), { target: { value: 'kid' } })
      fireEvent.change(screen.getByLabelText('Points (±)'), { target: { value: '-3' } })
      fireEvent.change(screen.getByLabelText('Why'), { target: { value: 'Fought over the remote' } })
      fireEvent.click(screen.getByRole('button', { name: 'Change points' }))
      expect(await screen.findByText('Took away 3 points.')).toBeTruthy()
      expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ user_id: 'kid', delta: -3, reason: 'Fought over the remote' })
    })

    it("shows the server's reason when saving fails", async () => {
      rewardsApi({ 'POST /rewards/badges': () => { throw apiError(422, 'threshold must be at least 1') } })
      signIn('mom', 'admin')
      renderApp(<RewardsPage />)
      tab('Manage')
      fireEvent.click(screen.getByRole('button', { name: '+ Badge' }))
      fireEvent.change(screen.getByLabelText('Badge'), { target: { value: 'X' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save badge' }))
      expect(await screen.findByText('threshold must be at least 1')).toBeTruthy()
    })
  })
})
