import { mockApi } from '../../test/api'

export const recipe = (id: string, title: string, over: object = {}) => ({
  id, title, description: null, servings: 4, prep_minutes: 10, cook_minutes: 20, ingredients: ['1 lb beef', '8 tortillas'],
  steps: ['Brown the beef.', 'Fill the tortillas.'], tags: ['dinner'], source_url: null, video_url: null,
  catalog_key: null, created_by: 'mom', ...over,
})

export const WEEK = {
  week_start: '2026-10-12',
  days: ['2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15', '2026-10-16', '2026-10-17', '2026-10-18'],
  entries: [{ id: 'e1', day: '2026-10-12', slot: 'dinner', recipe_id: 'r1', title: 'Tacos', note: null }],
}

export const shop = (id: string, name: string, over: object = {}) => ({
  id, name, quantity: null, source: 'manual', recipe_id: null, recipe_title: null, week_start: null, checked: false,
  checked_at: null, checked_by: null, in_pantry: null, ...over,
})

export const pantry = (id: string, name: string, over: object = {}) => ({
  id, name, quantity: 2, unit: 'lb', low_at: null, expires_on: null, is_low: false, expired: false, expires_soon: false, ...over,
})

export function mealsApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /meals/plan': (params: unknown) => ((params as { start?: string } | undefined)?.start
      ? { ...WEEK, week_start: (params as { start: string }).start, entries: [] } : WEEK),
    'GET /meals/recipes': [recipe('r1', 'Tacos'), recipe('r2', 'Pancakes', { tags: ['breakfast'], video_url: 'https://videos.example.com/p' })],
    'GET /meals/catalog': [{ ...recipe('x', 'Overnight oats'), key: 'overnight-oats', added: false },
      { ...recipe('y', 'Banana muffins'), key: 'banana-muffins', added: true }],
    'GET /meals/shopping': [shop('s1', '1 lb beef', { source: 'plan', recipe_title: 'Tacos', quantity: '×2' }),
      shop('s2', 'Rice', { in_pantry: 'Rice' }), shop('s3', 'Bread', { checked: true, checked_at: '2026-10-13T12:00:00+00:00' })],
    'GET /meals/shopping/history': [shop('h1', 'Milk', { checked: true, checked_at: '2026-10-05T12:00:00+00:00' })],
    'GET /meals/pantry': [pantry('p1', 'Milk', { is_low: true, expires_soon: true, expires_on: '2026-10-15', quantity: 0.5, unit: 'gal' }),
      pantry('p2', 'Yogurt', { expired: true }), pantry('p3', 'Flour')],
    ...extra,
  })
}
