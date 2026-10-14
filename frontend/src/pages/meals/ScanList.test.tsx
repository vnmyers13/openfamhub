import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../../stores/auth'
import { renderApp } from '../../test/render'
import { signIn } from '../chores/fixtures'
import { mealsApi, recipe } from './fixtures'
import MealsPage from './MealsPage'

const readText = vi.fn()
vi.mock('../../lib/ocr', async (orig) => ({ ...(await orig<typeof import('../../lib/ocr')>()), readText: (...a: unknown[]) => readText(...a) }))

const photo = () => new File(['png'], 'list.jpg', { type: 'image/jpeg' })
const openScan = async () => {
  fireEvent.click(screen.getByRole('tab', { name: 'Shopping list' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Scan a list' }))
  const dialog = screen.getByRole('dialog', { name: 'Scan a list' })
  fireEvent.change(within(dialog).getByLabelText('Take or choose a photo'), { target: { files: [photo()] } })
  return dialog
}

describe('Scan a list', () => {
  afterEach(() => {
    useAuthStore.getState().clearUser()
    vi.restoreAllMocks()
    readText.mockReset()
  })

  it('reads a photo, lets you fix it up, and adds what is ticked', async () => {
    readText.mockImplementation(async (_img: Blob, onProgress?: (p: { status: string; progress: number }) => void) => {
      onProgress?.({ status: 'recognizing text', progress: 0.5 })
      return 'Shopping list\n- 2 |b apples\n- Rice\n- bred\n- Eggs x 12\n~~\n'
    })
    const calls = mealsApi({ 'POST /meals/shopping': { id: 'n' } })
    signIn('kid', 'member')
    renderApp(<MealsPage />)
    const dialog = await openScan()
    await within(dialog).findByLabelText('Item 1')
    const name = (n: number) => within(dialog).getByLabelText(`Item ${n}`) as HTMLInputElement
    const tick = (n: number) => within(dialog).getByLabelText(`Add item ${n}`) as HTMLInputElement
    // Title and debris are left out; "Rice" is already on the list (fixtures), so it starts unticked.
    expect([1, 2, 3, 4].map((n) => [name(n).value, tick(n).checked])).toEqual([
      ['Apples', true], ['Rice', false], ['Bred', true], ['Eggs', true],
    ])
    expect(within(dialog).getByText('already on the list')).toBeTruthy()
    expect(within(dialog).getByText('Skipped: Shopping list, ~~')).toBeTruthy()
    expect((within(dialog).getByLabelText('How much for item 1') as HTMLInputElement).value).toBe('2 lb')
    fireEvent.change(name(3), { target: { value: 'Bread' } })
    fireEvent.click(tick(4))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Add 2 to the list' }))
    expect(await screen.findByText('Added 2 items from the photo.')).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.body)).toEqual([
      { name: 'Apples', quantity: '2 lb' }, { name: 'Bread', quantity: null },
    ])
  })

  it("says so when the photo can't be read or has no list on it, and lets you try another", async () => {
    readText.mockRejectedValueOnce(new Error('bad image')).mockResolvedValueOnce('~~ |\n.\n')
    mealsApi()
    signIn('kid', 'member')
    renderApp(<MealsPage />)
    const dialog = await openScan()
    expect(await within(dialog).findByText("Couldn't read that photo. Try again, or try another one.")).toBeTruthy()
    fireEvent.change(within(dialog).getByLabelText('Take or choose a photo'), { target: { files: [photo()] } })
    expect(await within(dialog).findByText('No list items found. Try a closer, brighter photo of the list.')).toBeTruthy()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('viewers have no scan button', async () => {
    mealsApi()
    signIn('gran', 'viewer')
    renderApp(<MealsPage />)
    fireEvent.click(screen.getByRole('tab', { name: 'Shopping list' }))
    await screen.findByText(/In the cart/)
    expect(screen.queryByRole('button', { name: 'Scan a list' })).toBeNull()
  })
})

describe('Recipe from a photo', () => {
  afterEach(() => {
    useAuthStore.getState().clearUser()
    vi.restoreAllMocks()
    readText.mockReset()
  })

  it('reads the photo into the paste box, joined up, for checking before it is read', async () => {
    readText.mockResolvedValue('Toast\n\nIngredients\n1 slice bread\nMethod\nToast the bread until\ngolden.\n')
    const calls = mealsApi({ 'POST /import/recipe': { ...recipe('', 'Toast'), id: undefined } })
    signIn('kid', 'member')
    renderApp(<MealsPage />)
    fireEvent.click(screen.getByRole('tab', { name: 'Recipes' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Import' }))
    fireEvent.change(screen.getByLabelText('Read a photo of a recipe'), { target: { files: [photo()] } })
    const box = await screen.findByDisplayValue(/Toast the bread until golden\./) as HTMLTextAreaElement
    expect(box.value).toBe('Toast\nIngredients\n1 slice bread\nMethod\nToast the bread until golden.')
    expect(screen.getByText('Check the text, then read it.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Read recipe' }))
    expect(await screen.findByDisplayValue('Toast')).toBeTruthy()
    expect(calls.find((c) => c.url === '/import/recipe')?.body).toEqual({ text: box.value })
  })

  it("says when a recipe photo can't be read", async () => {
    readText.mockRejectedValue(new Error('nope'))
    mealsApi()
    signIn('kid', 'member')
    renderApp(<MealsPage />)
    fireEvent.click(screen.getByRole('tab', { name: 'Recipes' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Import' }))
    fireEvent.change(screen.getByLabelText('Read a photo of a recipe'), { target: { files: [photo()] } })
    expect(await screen.findByText("Couldn't read that photo. Try a closer, brighter one, or paste the text.")).toBeTruthy()
  })
})
