import { describe, expect, it } from 'vitest'
import { recipeTextFromOcr } from './ocrRecipe'

describe('recipeTextFromOcr', () => {
  it('joins steps that wrapped onto the next line, and keeps headings and ingredient lines apart', () => {
    const ocr = [
      'Banana Bread', '', 'Serves 8', '', 'Ingredients', '3 ripe bananas', '1/3 cup melted butter', '1 cup sugar',
      '', 'Method', '1. Heat the oven to 350F and butter', 'a loaf pan.', '2. Mash the bananas, then stir in', 'the butter and sugar.',
      'Bake for 60 minutes', 'until a skewer comes out clean.',
    ].join('\n')
    expect(recipeTextFromOcr(ocr)).toBe([
      'Banana Bread', 'Serves 8', 'Ingredients', '3 ripe bananas', '1/3 cup melted butter', '1 cup sugar',
      'Method', '1. Heat the oven to 350F and butter a loaf pan.', '2. Mash the bananas, then stir in the butter and sugar.',
      'Bake for 60 minutes until a skewer comes out clean.',
    ].join('\n'))
  })

  it('tidies OCR debris and the usual letter swaps in headings', () => {
    expect(recipeTextFromOcr('Pancakes\n|ngredients\n~ |\n2 eggs\nDirections:\nWhisk  everything.')).toBe(
      'Pancakes\nIngredients\n2 eggs\nDirections:\nWhisk everything.')
  })

  it('never joins lines in the ingredients list, even lowercase ones', () => {
    expect(recipeTextFromOcr('Pesto\nIngredients\n2 cups basil\nsalt\nfresh pepper\nMethod\nBlend the basil with\nthe salt.')).toBe(
      'Pesto\nIngredients\n2 cups basil\nsalt\nfresh pepper\nMethod\nBlend the basil with the salt.')
  })

  it('leaves text with nothing to fix as it was', () => {
    expect(recipeTextFromOcr('Toast\nIngredients\n1 slice bread\nMethod\nToast it.')).toBe('Toast\nIngredients\n1 slice bread\nMethod\nToast it.')
  })
})
