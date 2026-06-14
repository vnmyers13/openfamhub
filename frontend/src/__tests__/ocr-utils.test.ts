import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { parseLines, classifyLines } from '@/lib/ocr-utils'

const createImageBitmapMock = vi.fn(async (source: Blob | HTMLImageElement | HTMLCanvasElement | ImageBitmap) => {
  if (source instanceof Blob && (source as any)._mockWidth) {
    return {
      width: (source as any)._mockWidth,
      height: (source as any)._mockHeight,
      close: () => {},
    } as ImageBitmap
  }
  return {
    width: 1920,
    height: 1440,
    close: () => {},
  } as ImageBitmap
})

vi.stubGlobal('createImageBitmap', createImageBitmapMock)

describe('parseLines', () => {
  it('extracts and trims non-empty text lines', () => {
    const result = {
      data: {
        lines: [
          { text: '  2 tbsp olive oil  ' },
          { text: '1 cup flour' },
          { text: '   ' },
          { text: '' },
          { text: '3 cloves garlic' },
        ],
      },
    }
    const lines = parseLines(result)
    expect(lines).toEqual(['2 tbsp olive oil', '1 cup flour', '3 cloves garlic'])
  })

  it('returns empty array when no lines', () => {
    const result = {
      data: {
        lines: [],
      },
    }
    const lines = parseLines(result)
    expect(lines).toEqual([])
  })

  it('filters out empty and whitespace-only lines', () => {
    const result = {
      data: {
        lines: [
          { text: '   ' },
          { text: '' },
          { text: '\t\n' },
        ],
      },
    }
    const lines = parseLines(result)
    expect(lines).toEqual([])
  })
})

describe('classifyLines', () => {
  it('flags lines with quantity+unit patterns as ingredients', () => {
    const lines = ['2 tbsp olive oil', '1 cup flour', '3 oz butter']
    const result = classifyLines(lines)
    expect(result.ingredients).toEqual(['2 tbsp olive oil', '1 cup flour', '3 oz butter'])
    expect(result.steps).toEqual([])
  })

  it('handles lines without clear patterns as steps', () => {
    const lines = ['Preheat oven to 350F', 'Mix dry ingredients', 'Bake for 30 minutes']
    const result = classifyLines(lines)
    expect(result.ingredients).toEqual([])
    expect(result.steps).toEqual(['Preheat oven to 350F', 'Mix dry ingredients', 'Bake for 30 minutes'])
  })

  it('handles all lines as ingredients', () => {
    const lines = ['2 tbsp olive oil', '1 cup flour', '3 oz butter']
    const result = classifyLines(lines)
    expect(result.ingredients).toHaveLength(3)
    expect(result.steps).toHaveLength(0)
  })

  it('recognizes mixed content with ingredients and steps', () => {
    const lines = [
      '2 tbsp olive oil',
      'Preheat oven to 350F',
      '1 cup flour',
      'Mix together',
      '3 oz butter',
    ]
    const result = classifyLines(lines)
    expect(result.ingredients).toEqual(['2 tbsp olive oil', '1 cup flour', '3 oz butter'])
    expect(result.steps).toEqual(['Preheat oven to 350F', 'Mix together'])
  })

  it('recognizes tbsp unit keyword', () => {
    const result = classifyLines(['2 tbsp sugar'])
    expect(result.ingredients).toEqual(['2 tbsp sugar'])
  })

  it('recognizes cup unit keyword', () => {
    const result = classifyLines(['1 cup milk'])
    expect(result.ingredients).toEqual(['1 cup milk'])
  })

  it('recognizes cups unit keyword', () => {
    const result = classifyLines(['2 cups water'])
    expect(result.ingredients).toEqual(['2 cups water'])
  })

  it('recognizes oz unit keyword', () => {
    const result = classifyLines(['8 oz cream cheese'])
    expect(result.ingredients).toEqual(['8 oz cream cheese'])
  })

  it('recognizes g unit keyword', () => {
    const result = classifyLines(['100 g chocolate'])
    expect(result.ingredients).toEqual(['100 g chocolate'])
  })

  it('recognizes kg unit keyword', () => {
    const result = classifyLines(['1 kg potatoes'])
    expect(result.ingredients).toEqual(['1 kg potatoes'])
  })

  it('recognizes large unit keyword', () => {
    const result = classifyLines(['2 large eggs'])
    expect(result.ingredients).toEqual(['2 large eggs'])
  })

  it('recognizes small unit keyword', () => {
    const result = classifyLines(['1 small onion'])
    expect(result.ingredients).toEqual(['1 small onion'])
  })

  it('recognizes pinch unit keyword', () => {
    const result = classifyLines(['1 pinch of salt'])
    expect(result.ingredients).toEqual(['1 pinch of salt'])
  })

  it('recognizes dash unit keyword', () => {
    const result = classifyLines(['1 dash of vanilla'])
    expect(result.ingredients).toEqual(['1 dash of vanilla'])
  })

  it('recognizes clove unit keyword', () => {
    const result = classifyLines(['3 clove garlic'])
    expect(result.ingredients).toEqual(['3 clove garlic'])
  })

  it('recognizes can unit keyword', () => {
    const result = classifyLines(['1 can diced tomatoes'])
    expect(result.ingredients).toEqual(['1 can diced tomatoes'])
  })

  it('recognizes lb unit keyword', () => {
    const result = classifyLines(['1 lb ground beef'])
    expect(result.ingredients).toEqual(['1 lb ground beef'])
  })

  it('recognizes package unit keyword', () => {
    const result = classifyLines(['1 package ramen'])
    expect(result.ingredients).toEqual(['1 package ramen'])
  })

  it('recognizes slice unit keyword', () => {
    const result = classifyLines(['4 slice bread'])
    expect(result.ingredients).toEqual(['4 slice bread'])
  })

  it('recognizes piece unit keyword', () => {
    const result = classifyLines(['2 piece chicken'])
    expect(result.ingredients).toEqual(['2 piece chicken'])
  })

  it('recognizes whole unit keyword', () => {
    const result = classifyLines(['1 whole lemon'])
    expect(result.ingredients).toEqual(['1 whole lemon'])
  })

  it('recognizes quarter unit keyword', () => {
    const result = classifyLines(['1/4 cup butter'])
    expect(result.ingredients).toEqual(['1/4 cup butter'])
  })

  it('recognizes half unit keyword', () => {
    const result = classifyLines(['1/2 tsp salt'])
    expect(result.ingredients).toEqual(['1/2 tsp salt'])
  })

  it('recognizes diced unit keyword', () => {
    const result = classifyLines(['2 diced tomatoes'])
    expect(result.ingredients).toEqual(['2 diced tomatoes'])
  })

  it('recognizes chopped unit keyword', () => {
    const result = classifyLines(['1 chopped onion'])
    expect(result.ingredients).toEqual(['1 chopped onion'])
  })

  it('recognizes minced unit keyword', () => {
    const result = classifyLines(['2 minced garlic'])
    expect(result.ingredients).toEqual(['2 minced garlic'])
  })

  it('recognizes liquid unit keyword', () => {
    const result = classifyLines(['2 liquid tablespoons'])
    expect(result.ingredients).toEqual(['2 liquid tablespoons'])
  })

  it('recognizes ml unit keyword', () => {
    const result = classifyLines(['500 ml water'])
    expect(result.ingredients).toEqual(['500 ml water'])
  })

  it('recognizes liter unit keyword', () => {
    const result = classifyLines(['1 liter soda'])
    expect(result.ingredients).toEqual(['1 liter soda'])
  })

  it('recognizes tablespoon unit keyword', () => {
    const result = classifyLines(['2 tablespoon honey'])
    expect(result.ingredients).toEqual(['2 tablespoon honey'])
  })

  it('recognizes teaspoon unit keyword', () => {
    const result = classifyLines(['1 teaspoon vanilla'])
    expect(result.ingredients).toEqual(['1 teaspoon vanilla'])
  })

  it('handles decimal quantities', () => {
    const result = classifyLines(['0.5 cup sugar'])
    expect(result.ingredients).toEqual(['0.5 cup sugar'])
  })

  it('handles mixed fractions and decimals', () => {
    const result = classifyLines(['1.5 cups broth'])
    expect(result.ingredients).toEqual(['1.5 cups broth'])
  })
})

describe('compressImage', () => {
  let originalCreateElement: typeof document.createElement

  beforeEach(() => {
    vi.clearAllMocks()
    originalCreateElement = document.createElement.bind(document)
  })

  afterEach(() => {
    document.createElement = originalCreateElement
  })

  it('resizes image to max 1920px width', async () => {
    const { compressImage } = await import('@/lib/ocr-utils')

    let capturedWidth = 0
    let capturedHeight = 0

    document.createElement = ((tagName: string) => {
      const el = originalCreateElement(tagName)
      if (tagName === 'canvas') {
        ;(el as any).getContext = ((contextType: string) => {
          if (contextType === '2d') {
            return {
              drawImage: (
                _bitmap: ImageBitmap,
                _x: number,
                _y: number,
                w: number,
                h: number
              ) => {
                capturedWidth = w
                capturedHeight = h
              },
              toDataURL: () => 'data:image/jpeg;base64,fake',
            }
          }
          return null
        }) as any
        ;(el as any).toBlob = ((cb: (blob: Blob | null) => void) => {
          cb(new Blob(['fakejpeg'], { type: 'image/jpeg' }))
        }) as any
        ;(el as any).width = 1920
        ;(el as any).height = 1
      }
      return el
    }) as any

    const largeBlob = new Blob(['test'], { type: 'image/jpeg' })
    ;(largeBlob as any)._mockWidth = 4000
    ;(largeBlob as any)._mockHeight = 3000

    const result = await compressImage(largeBlob)
    expect(result.width).toBeLessThanOrEqual(1920)
    expect(result.height).toBeLessThanOrEqual(1440)
    expect(createImageBitmapMock).toHaveBeenCalledTimes(2)
    expect(capturedWidth).toBe(1920)
    expect(capturedHeight).toBe(1440)
    result.close()
  })

  it('leaves small images unchanged', async () => {
    const { compressImage } = await import('@/lib/ocr-utils')

    const smallBlob = new Blob(['test'], { type: 'image/jpeg' })
    ;(smallBlob as any)._mockWidth = 800
    ;(smallBlob as any)._mockHeight = 600

    const result = await compressImage(smallBlob)
    expect(result.width).toBe(800)
    expect(result.height).toBe(600)
    expect(createImageBitmapMock).toHaveBeenCalledTimes(1)
    result.close()
  })
})
