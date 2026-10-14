import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../../stores/auth'
import { apiError } from '../../test/api'
import { renderApp } from '../../test/render'
import { signIn } from '../chores/fixtures'
import { mealsApi, recipe } from './fixtures'
import MealsPage from './MealsPage'

const tab = (name: string) => fireEvent.click(screen.getByRole('tab', { name }))
const writes = (calls: { method: string; url: string; body: unknown }[]) => calls.filter((c) => c.method !== 'GET')

describe('MealsPage', () => {
  afterEach(() => {
    useAuthStore.getState().clearUser()
    vi.restoreAllMocks()
  })

  describe('This week', () => {
    it('shows the week and plans a meal from a recipe or typed in', async () => {
      const calls = mealsApi({ 'PUT /meals/plan/2026-10-13/lunch': {}, 'PUT /meals/plan/2026-10-14/dinner': {}, 'DELETE /meals/plan/2026-10-12/dinner': null })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      expect(await screen.findByText('Oct 12 – 18')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Lunch on Tue 13: nothing planned' }))
      await screen.findByRole('option', { name: 'Pancakes' })
      fireEvent.change(screen.getByLabelText('Recipe for Lunch on Tue 13'), { target: { value: 'r2' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save' }))
      await waitFor(() => expect(writes(calls)).toHaveLength(1))
      fireEvent.click(screen.getByRole('button', { name: 'Dinner on Wed 14: nothing planned' }))
      fireEvent.change(screen.getByLabelText("What's for Dinner on Wed 14"), { target: { value: 'Leftovers' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save' }))
      await waitFor(() => expect(writes(calls)).toHaveLength(2))
      fireEvent.click(screen.getByRole('button', { name: 'Dinner on Mon 12: Tacos' }))
      fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
      await waitFor(() => expect(writes(calls).map((c) => [c.method, c.url, c.body])).toEqual([
        ['PUT', '/meals/plan/2026-10-13/lunch', { recipe_id: 'r2', title: null }],
        ['PUT', '/meals/plan/2026-10-14/dinner', { recipe_id: null, title: 'Leftovers' }],
        ['DELETE', '/meals/plan/2026-10-12/dinner', undefined],
      ]))
    })

    it('moves between weeks and makes the shopping list', async () => {
      const calls = mealsApi({ 'POST /meals/shopping/from-plan': { added: 5, removed: 1, week_start: '2026-10-12' } })
      signIn('mom', 'admin')
      renderApp(<MealsPage />)
      fireEvent.click(await screen.findByRole('button', { name: 'Make shopping list' }))
      expect(await screen.findByText(/Shopping list updated: 5 added, 1 removed\./)).toBeTruthy()
      expect(calls.find((c) => c.url === '/meals/shopping/from-plan')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Next week' }))
      expect(await screen.findByText('Oct 19 – 25')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'This week' }))
      expect(await screen.findByText('Oct 12 – 18')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Open the list' }))
      expect(await screen.findByLabelText('New item')).toBeTruthy()
    })

    it('viewers see the plan but cannot change it', async () => {
      mealsApi()
      signIn('gm', 'viewer')
      renderApp(<MealsPage />)
      const slot = await screen.findByRole('button', { name: 'Dinner on Mon 12: Tacos' })
      expect((slot as HTMLButtonElement).disabled).toBe(true)
      expect(screen.queryByRole('button', { name: 'Make shopping list' })).toBeNull()
    })
  })

  describe('Recipes', () => {
    it('searches, filters by tag, opens a recipe and cooks it step by step', async () => {
      mealsApi({
        'GET /meals/recipes': (params: unknown) => {
          const p = (params ?? {}) as { q?: string; tag?: string }
          const all = [recipe('r1', 'Tacos'), recipe('r2', 'Pancakes', { tags: ['breakfast'], video_url: 'https://videos.example.com/p' })]
          return all.filter((r) => (!p.q || r.title.toLowerCase().includes(p.q)) && (!p.tag || r.tags.includes(p.tag)))
        },
      })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Recipes')
      expect(await screen.findByText('Tacos')).toBeTruthy()
      fireEvent.change(screen.getByLabelText('Filter by tag'), { target: { value: 'breakfast' } })
      await waitFor(() => expect(screen.queryByText('Tacos')).toBeNull())
      fireEvent.change(screen.getByLabelText('Filter by tag'), { target: { value: '' } })
      fireEvent.change(screen.getByLabelText('Search recipes'), { target: { value: 'pan' } })
      await waitFor(() => expect(screen.queryByText('Tacos')).toBeNull())
      fireEvent.click(screen.getByText('Pancakes'))
      expect(await screen.findByRole('heading', { name: 'Pancakes' })).toBeTruthy()
      expect(screen.getByText('Serves 4 · Prep 10 min · Cook 20 min')).toBeTruthy()
      expect(screen.getByRole('link', { name: '▶ Watch the video' }).getAttribute('href')).toBe('https://videos.example.com/p')
      fireEvent.click(screen.getByRole('button', { name: 'Cook step by step' }))
      const cook = screen.getByRole('dialog', { name: 'Cooking Pancakes' })
      expect(within(cook).getByText('Step 1 of 2')).toBeTruthy()
      fireEvent.click(within(cook).getByRole('button', { name: 'Next' }))
      expect(within(cook).getByText('Fill the tortillas.')).toBeTruthy()
      fireEvent.click(within(cook).getByRole('button', { name: 'Back' }))
      expect(within(cook).getByText('Brown the beef.')).toBeTruthy()
      fireEvent.click(within(cook).getByRole('button', { name: 'Next' }))
      fireEvent.click(within(cook).getByRole('button', { name: 'Finished' }))
      expect(screen.queryByRole('dialog')).toBeNull()
      fireEvent.click(screen.getByRole('button', { name: '← All recipes' }))
      expect(await screen.findByLabelText('Search recipes')).toBeTruthy()
    })

    it('scales ingredients by servings, or by a multiplier when servings are unknown', async () => {
      mealsApi({ 'GET /meals/recipes': [recipe('r1', 'Tacos', { servings: 4, ingredients: ['1 1/2 lb beef', 'Salsa to serve'] }),
        recipe('r3', 'Mystery stew', { servings: null, ingredients: ['2 cups beans'] })] })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Recipes')
      fireEvent.click(await screen.findByText('Tacos'))
      for (let i = 0; i < 4; i++) fireEvent.click(screen.getByRole('button', { name: 'More servings' }))
      expect(screen.getByText('Serves 8')).toBeTruthy()
      expect(screen.getByText('3 lb beef')).toBeTruthy()
      expect(screen.getByText('Salsa to serve')).toBeTruthy()
      expect(screen.getByText(/Amounts at the start of each line are scaled/)).toBeTruthy()
      for (let i = 0; i < 6; i++) fireEvent.click(screen.getByRole('button', { name: 'Fewer servings' }))
      expect(screen.getByText('3/4 lb beef')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: '← All recipes' }))
      fireEvent.click(await screen.findByText('Mystery stew'))
      fireEvent.click(screen.getByRole('button', { name: '½×' }))
      expect(screen.getByText('1 cups beans')).toBeTruthy()
    })

    it('adds a recipe from the form', async () => {
      const calls = mealsApi({ 'POST /meals/recipes': recipe('r9', 'Soup') })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Recipes')
      fireEvent.click(await screen.findByRole('button', { name: '+ Recipe' }))
      fireEvent.change(screen.getByLabelText('Recipe'), { target: { value: 'Soup' } })
      fireEvent.change(screen.getByLabelText('Serves'), { target: { value: '6' } })
      fireEvent.change(screen.getByLabelText(/^Tags/), { target: { value: 'dinner, vegetarian' } })
      fireEvent.change(screen.getByLabelText('Ingredients, one per line'), { target: { value: '1 onion\n\n4 cups broth' } })
      fireEvent.change(screen.getByLabelText('Steps, one per line'), { target: { value: 'Simmer.' } })
      fireEvent.change(screen.getByLabelText('Video (link)'), { target: { value: 'https://v.example.com/soup' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save recipe' }))
      await waitFor(() => expect(writes(calls)[0]?.body).toEqual({
        id: undefined, title: 'Soup', description: null, servings: 6, prep_minutes: null, cook_minutes: null,
        tags: ['dinner', 'vegetarian'], ingredients: ['1 onion', '4 cups broth'], steps: ['Simmer.'],
        source_url: null, video_url: 'https://v.example.com/soup',
      }))
    })

    it('imports a recipe from a link and saves the reviewed draft', async () => {
      const calls = mealsApi({
        'POST /import/recipe': { ...recipe('', 'Chili'), id: undefined, source_url: 'https://food.example.com/chili' },
        'POST /meals/recipes': recipe('r5', 'Chili'),
      })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Recipes')
      fireEvent.click(await screen.findByRole('button', { name: 'Import' }))
      fireEvent.change(screen.getByLabelText('Recipe link'), { target: { value: 'https://food.example.com/chili' } })
      fireEvent.click(screen.getByRole('button', { name: 'Read recipe' }))
      expect(await screen.findByDisplayValue('Chili')).toBeTruthy()
      expect(calls.find((c) => c.url === '/import/recipe')?.body).toEqual({ url: 'https://food.example.com/chili' })
      fireEvent.click(screen.getByRole('button', { name: 'Save recipe' }))
      await waitFor(() => expect(calls.find((c) => c.url === '/meals/recipes' && c.method === 'POST')).toBeTruthy())
    })

    it("explains when an import finds nothing", async () => {
      const calls = mealsApi({ 'POST /import/recipe': () => { throw apiError(400, 'No recipe found on that page. Paste the recipe text instead.') } })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Recipes')
      fireEvent.click(await screen.findByRole('button', { name: 'Import' }))
      fireEvent.change(screen.getByLabelText('Paste the recipe'), { target: { value: 'something' } })
      fireEvent.click(screen.getByRole('button', { name: 'Read recipe' }))
      expect(await screen.findByText(/No recipe found on that page/)).toBeTruthy()
      expect(calls.find((c) => c.url === '/import/recipe')?.body).toEqual({ text: 'something' })
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    })

    it('adds ideas from the catalog', async () => {
      const calls = mealsApi({ 'POST /meals/catalog/overnight-oats': recipe('r7', 'Overnight oats') })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Recipes')
      fireEvent.click(await screen.findByRole('button', { name: 'Recipe ideas' }))
      expect(await screen.findByText('In your recipes')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Add: Overnight oats' }))
      await waitFor(() => expect(calls.some((c) => c.url === '/meals/catalog/overnight-oats')).toBe(true))
      fireEvent.click(screen.getByRole('button', { name: 'Back to my recipes' }))
    })

    it('edits and deletes a recipe after confirming', async () => {
      const calls = mealsApi({ 'PATCH /meals/recipes/r1': recipe('r1', 'Fish tacos'), 'DELETE /meals/recipes/r1': null })
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      signIn('mom', 'admin')
      renderApp(<MealsPage />)
      tab('Recipes')
      fireEvent.click(await screen.findByText('Tacos'))
      fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
      fireEvent.change(screen.getByLabelText('Recipe'), { target: { value: 'Fish tacos' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save recipe' }))
      fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
      await waitFor(() => expect(writes(calls).map((c) => [c.method, c.url])).toEqual([
        ['PATCH', '/meals/recipes/r1'], ['DELETE', '/meals/recipes/r1']]))
    })
  })

  describe('Shopping list', () => {
    it('shows where items came from and what the pantry may cover', async () => {
      mealsApi()
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Shopping list')
      expect(await screen.findByText('for Tacos')).toBeTruthy()
      expect(screen.getByText('you may have Rice')).toBeTruthy()
      expect(screen.getByText('In the cart (1)')).toBeTruthy()
    })

    it('adds, ticks off, removes, fills from the plan and finishes shopping', async () => {
      const calls = mealsApi({
        'POST /meals/shopping': { id: 'n' }, 'PATCH /meals/shopping/s2': {}, 'DELETE /meals/shopping/s1': null,
        'POST /meals/shopping/from-plan': { added: 3, removed: 0, week_start: '2026-10-12' },
        'POST /meals/shopping/clear-checked': { archived: 1 },
      })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Shopping list')
      fireEvent.change(await screen.findByLabelText('New item'), { target: { value: 'Coffee' } })
      fireEvent.change(screen.getByLabelText('How much'), { target: { value: '1 bag' } })
      fireEvent.click(screen.getByRole('button', { name: 'Add' }))
      await waitFor(() => expect(writes(calls)).toHaveLength(1))
      fireEvent.click(await screen.findByLabelText('Bought: Rice'))
      await waitFor(() => expect(writes(calls)).toHaveLength(2))
      fireEvent.click(screen.getByRole('button', { name: 'Remove: 1 lb beef' }))
      await waitFor(() => expect(writes(calls)).toHaveLength(3))
      fireEvent.click(screen.getByRole('button', { name: "Add this week's meals" }))
      expect(await screen.findByText("Added 3 from this week's meals.")).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Done shopping' }))
      await waitFor(() => expect(writes(calls).map((c) => [c.method, c.url, c.body])).toEqual([
        ['POST', '/meals/shopping', { name: 'Coffee', quantity: '1 bag' }],
        ['PATCH', '/meals/shopping/s2', { checked: true }],
        ['DELETE', '/meals/shopping/s1', undefined],
        ['POST', '/meals/shopping/from-plan', undefined],
        ['POST', '/meals/shopping/clear-checked', undefined],
      ]))
      fireEvent.click(screen.getByRole('button', { name: 'Show history' }))
      expect(await screen.findByText(/^Milk/)).toBeTruthy()
    })

    it("shows the server's reason when something fails", async () => {
      mealsApi({ 'POST /meals/shopping': () => { throw apiError(422, 'name is too long') } })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Shopping list')
      fireEvent.change(await screen.findByLabelText('New item'), { target: { value: 'x' } })
      fireEvent.click(screen.getByRole('button', { name: 'Add' }))
      expect(await screen.findByText('name is too long')).toBeTruthy()
    })
  })

  describe('Pantry', () => {
    it('flags what is low, expiring or expired and restocks it', async () => {
      const calls = mealsApi({ 'POST /meals/pantry/restock': { added: 2 } })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Pantry')
      expect(await screen.findByText('Running low')).toBeTruthy()
      expect(screen.getByText('Use soon')).toBeTruthy()
      expect(screen.getByText('Expired')).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Put 2 low or expired on the list' }))
      expect(await screen.findByText('Added 2 to the shopping list.')).toBeTruthy()
      expect(calls.some((c) => c.url === '/meals/pantry/restock')).toBe(true)
    })

    it('adds, edits and removes items', async () => {
      const calls = mealsApi({ 'POST /meals/pantry': {}, 'PATCH /meals/pantry/p3': {}, 'DELETE /meals/pantry/p2': null })
      signIn('kid', 'member')
      renderApp(<MealsPage />)
      tab('Pantry')
      fireEvent.click(await screen.findByRole('button', { name: '+ Item' }))
      fireEvent.change(screen.getByLabelText('Item'), { target: { value: 'Rice' } })
      fireEvent.change(screen.getByLabelText('Have'), { target: { value: '3' } })
      fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'lb' } })
      fireEvent.change(screen.getByLabelText('Low at'), { target: { value: '1' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save' }))
      await waitFor(() => expect(writes(calls)).toHaveLength(1))
      fireEvent.click(await screen.findByRole('button', { name: 'Edit: Flour' }))
      fireEvent.change(screen.getByLabelText('Use by'), { target: { value: '2026-12-01' } })
      fireEvent.click(screen.getByRole('button', { name: 'Save' }))
      await waitFor(() => expect(writes(calls)).toHaveLength(2))
      fireEvent.click(await screen.findByRole('button', { name: 'Remove: Yogurt' }))
      await waitFor(() => expect(writes(calls).map((c) => [c.method, c.url, c.body])).toEqual([
        ['POST', '/meals/pantry', { id: undefined, name: 'Rice', quantity: 3, unit: 'lb', low_at: 1, expires_on: null }],
        ['PATCH', '/meals/pantry/p3', { name: 'Flour', quantity: 2, unit: 'lb', low_at: null, expires_on: '2026-12-01' }],
        ['DELETE', '/meals/pantry/p2', undefined],
      ]))
    })

    it('viewers only look', async () => {
      mealsApi()
      signIn('gm', 'viewer')
      renderApp(<MealsPage />)
      tab('Pantry')
      expect(await screen.findByText('Flour')).toBeTruthy()
      expect(screen.queryByRole('button', { name: '+ Item' })).toBeNull()
      expect(screen.queryByRole('button', { name: /Remove:/ })).toBeNull()
    })
  })
})
