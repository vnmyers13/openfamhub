export function parseLines(result: { data: { lines: { text: string; boundingbox?: string[] }[] } }): string[] {
  return result.data.lines.map(line => line.text.trim()).filter(text => text.length > 0)
}

export function classifyLines(lines: string[]): { ingredients: string[], steps: string[] } {
  const unitKeywords = [
    'tbsp', 'cup', 'cups', 'tablespoon', 'tsp', 'teaspoon',
    'oz', 'ounce', 'ounces', 'g', 'gram', 'grams', 'kg',
    'kilogram', 'lb', 'pounds', 'package', 'packages',
    'can', 'cans', 'large', 'small', 'pinch', 'dash',
    'clove', 'slice', 'slices', 'piece', 'pieces', 'whole',
    'quarter', 'half', 'diced', 'chopped', 'minced',
    'liquid', 'ml', 'liter', 'liters',
  ]

  const pattern = new RegExp(`(?:^|\\s)(\\d+\\s*[\\/\\.]?\\s*\\d*\\s*(?:${unitKeywords.join('|')}))\\b`, 'i')

  const ingredients: string[] = []
  const steps: string[] = []

  for (const line of lines) {
    if (pattern.test(line)) {
      ingredients.push(line)
    } else {
      steps.push(line)
    }
  }

  return { ingredients, steps }
}

export async function compressImage(blob: Blob): Promise<ImageBitmap> {
  const bitmap = await createImageBitmap(blob)
  const maxWidth = 1920

  if (bitmap.width <= maxWidth) {
    return bitmap
  }

  const scaleFactor = maxWidth / bitmap.width
  const newHeight = Math.round(bitmap.height * scaleFactor)

  const canvas = document.createElement('canvas')
  canvas.width = maxWidth
  canvas.height = newHeight

  const ctx = canvas.getContext('2d')
  if (!ctx) {
    bitmap.close()
    throw new Error('Could not get canvas context')
  }

  ctx.drawImage(bitmap, 0, 0, maxWidth, newHeight)
  bitmap.close()

  const compressedBlob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob)
        else reject(new Error('Canvas toBlob failed'))
      },
      'image/jpeg',
      0.8
    )
  })

  return createImageBitmap(compressedBlob)
}

export async function bitmapToBlob(bitmap: ImageBitmap): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = bitmap.width
  canvas.height = bitmap.height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Could not get canvas context')
  ctx.drawImage(bitmap, 0, 0)
  bitmap.close()
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob)
        else reject(new Error('Canvas toBlob failed'))
      },
      'image/jpeg',
      0.8
    )
  })
}
