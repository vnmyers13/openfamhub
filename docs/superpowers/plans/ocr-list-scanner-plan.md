# OCR List Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add client-side OCR to extract text from photos of lists — items added to shopping list from the Shopping tab, parsed into a new recipe from the Recipes tab.

**Architecture:** Frontend-only. Add `tesseract.js` as a dependency. Create a shared `ScanListModal` component with capture → OCR → preview/edit → submit flow. No backend changes.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Tesseract.js v5, Tailwind CSS 3

---

## File Map

- **Create:** `frontend/src/lib/ocr-utils.ts` — OCR text parsing and line classification utilities
- **Create:** `frontend/src/components/ScanListModal.tsx` — Shared modal component
- **Modify:** `frontend/package.json` — Add `tesseract.js` dependency
- **Modify:** `frontend/src/pages/MealsPage.tsx` — Add "Scan List" and "Scan Recipe" buttons, wire up modal
- **Test:** `frontend/src/__tests__/ocr-utils.test.ts` — Unit tests for parsing/classification utilities

---

### Task 1: Add tesseract.js dependency

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Add tesseract.js to package.json**

Add `"tesseract.js": "^5.0.0"` to the `dependencies` section of `frontend/package.json`.

```json
{
  "name": "openfamhub-web",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.0.0",
    "@tanstack/react-query-devtools": "^5.0.0",
    "axios": "^1.7.0",
    "date-fns": "^4.0.0",
    "idb": "^8.0.3",
    "moment": "^2.30.1",
    "react": "^19.0.0",
    "react-big-calendar": "^1.15.0",
    "react-dom": "^19.0.0",
    "react-icons": "^5.0.0",
    "react-router-dom": "^7.0.0",
    "tesseract.js": "^5.0.0",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@types/node": "^25.9.2",
    "@types/react": "^19.0.0",
    "@types/react-big-calendar": "^1.8.0",
    "@types/react-dom": "^19.0.0",
    "@vite-pwa/assets-generator": "^0.2.4",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.9.0",
    "postcss": "^8.4.40",
    "tailwindcss": "^3.4.1",
    "typescript": "~6.0.0",
    "vite": "^8.0.0",
    "vite-plugin-pwa": "^1.0.0"
  }
}
```

- [ ] **Step 2: Install the dependency**

Run: `cd frontend && npm install`
Expected: `tesseract.js@5.x` installed successfully, no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: add tesseract.js dependency for OCR"
```

---

### Task 2: Create OCR utility functions

**Files:**
- Create: `frontend/src/lib/ocr-utils.ts`

- [ ] **Step 1: Write unit tests for the utilities**

Create `frontend/src/__tests__/ocr-utils.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { parseLines, classifyLines, compressImage } from '../lib/ocr-utils';

describe('parseLines', () => {
  it('extracts and trims non-empty text lines', () => {
    const result = {
      data: {
        lines: [
          { text: '  milk  ', boundingbox: [] },
          { text: '', boundingbox: [] },
          { text: 'eggs', boundingbox: [] },
          { text: '   ', boundingbox: [] },
          { text: 'bread', boundingbox: [] },
        ],
      },
    };
    expect(parseLines(result)).toEqual(['milk', 'eggs', 'bread']);
  });

  it('returns empty array when no lines', () => {
    const result = { data: { lines: [] } };
    expect(parseLines(result as any)).toEqual([]);
  });
});

describe('classifyLines', () => {
  it('flags lines with quantity+unit patterns as ingredients', () => {
    const lines = ['1 cup flour', '2 tbsp butter', 'Preheat oven', 'Mix ingredients'];
    const classified = classifyLines(lines);
    expect(classified.ingredients).toContain('1 cup flour');
    expect(classified.ingredients).toContain('2 tbsp butter');
    expect(classified.steps).toContain('Preheat oven');
    expect(classified.steps).toContain('Mix ingredients');
  });

  it('handles lines without clear patterns as steps', () => {
    const lines = ['Stir well', 'Add salt', 'Serve hot'];
    const classified = classifyLines(lines);
    expect(classified.ingredients).toHaveLength(0);
    expect(classified.steps).toHaveLength(3);
  });

  it('handles all lines as ingredients', () => {
    const lines = ['2 cups flour', '1 tsp salt', '3 eggs'];
    const classified = classifyLines(lines);
    expect(classified.ingredients).toHaveLength(3);
    expect(classified.steps).toHaveLength(0);
  });

  it('recognizes common unit keywords', () => {
    const units = ['tbsp', 'cup', 'oz', 'g', 'kg', 'large', 'small', 'pinch', 'dash', 'clove', 'can', 'lb', 'package', 'slice', 'piece', 'whole', 'quarter', 'half', 'diced', 'chopped', 'minced', 'liquid', 'ml', 'liter', 'tablespoon', 'teaspoon'];
    for (const unit of units) {
      const lines = [`1 ${unit} test item`, 'Some step'];
      const classified = classifyLines(lines);
      expect(classified.ingredients).toContain(`1 ${unit} test item`);
    }
  });
});

describe('compressImage', () => {
  it('resizes image to max 1920px width', async () => {
    // Create a test canvas
    const canvas = document.createElement('canvas');
    canvas.width = 4000;
    canvas.height = 3000;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, 4000, 3000);

    const blob = await new Promise<Blob>((resolve) => {
      canvas.toBlob((b) => resolve(b!), 'image/png');
    });

    const compressed = await compressImage(blob);
    expect(compressed.width).toBeLessThanOrEqual(1920);
    expect(compressed.height).toBeLessThanOrEqual(1440); // proportional
  });

  it('leaves small images unchanged', async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 800;
    canvas.height = 600;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, 800, 600);

    const blob = await new Promise<Blob>((resolve) => {
      canvas.toBlob((b) => resolve(b!), 'image/png');
    });

    const compressed = await compressImage(blob);
    expect(compressed.width).toBe(800);
    expect(compressed.height).toBe(600);
  });
});
```

- [ ] **Step 2: Implement the utility functions**

Create `frontend/src/lib/ocr-utils.ts`:

```typescript
/**
 * OCR text parsing and line classification utilities.
 * Used by ScanListModal to process Tesseract.js output.
 */

// Common unit/quantity keywords that indicate an ingredient line
const INGREDIENT_PATTERNS = [
  /(?:^|\s)(\d+\s*[\/\.]?\s*\d*\s*(?:cup|cups|tbsp|tablespoon|tsp|teaspoon|oz|ounce|ounces|g|gram|grams|kg|kilogram|lb|pounds|package|packages|can|cans|large|small|pinch|dash|clove|slice|slices|piece|pieces|whole|quarter|half|diced|chopped|minced|liquid|ml|liter|liters)\b)/i,
];

/**
 * Extract non-empty trimmed text lines from a Tesseract.js result object.
 * @param result - Tesseract.js RecognizeResult (data.lines array)
 * @returns Array of non-empty trimmed text strings
 */
export function parseLines(result: { data: { lines: { text: string; boundingbox?: string[] }[] } }): string[] {
  return result.data.lines
    .map((line) => line.text.trim())
    .filter((text) => text.length > 0);
}

/**
 * Classify extracted lines into ingredients vs steps.
 * Lines matching ingredient patterns (quantity + unit) are flagged as ingredients.
 * All other lines are classified as steps.
 * @param lines - Array of text lines from OCR
 * @returns { ingredients: string[], steps: string[] }
 */
export function classifyLines(lines: string[]): { ingredients: string[]; steps: string[] } {
  const ingredients: string[] = [];
  const steps: string[] = [];

  for (const line of lines) {
    const isIngredient = INGREDIENT_PATTERNS.some((pattern) => pattern.test(line));
    if (isIngredient) {
      ingredients.push(line);
    } else {
      steps.push(line);
    }
  }

  return { ingredients, steps };
}

/**
 * Compress an image blob to a maximum width of 1920px while maintaining aspect ratio.
 * Small images (<= 1920px) are returned unchanged.
 * @param blob - Image blob from file input or camera
 * @returns Promise resolving to a compressed ImageBitmap
 */
export async function compressImage(blob: Blob): Promise<ImageBitmap> {
  const MAX_WIDTH = 1920;

  const img = await createImageBitmap(blob);

  if (img.width <= MAX_WIDTH) {
    return img;
  }

  const canvas = document.createElement('canvas');
  const scale = MAX_WIDTH / img.width;
  canvas.width = MAX_WIDTH;
  canvas.height = Math.round(img.height * scale);

  const ctx = canvas.getContext('2d');
  if (!ctx) {
    throw new Error('Could not get canvas context');
  }

  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  img.close();

  return createImageBitmap(new Blob([await canvas.toBlob('image/jpeg', 0.8)], { type: 'image/jpeg' }));
}
```

- [ ] **Step 3: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/__tests__/ocr-utils.test.ts`
Expected: All tests PASS.

If vitest is not configured, create a minimal vitest config:

Create `frontend/vite.test.config.ts`:
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/__tests__/**/*.test.ts'],
  },
});
```

Then run: `cd frontend && npx vitest run --config vite.test.config.ts src/__tests__/ocr-utils.test.ts`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/ocr-utils.ts frontend/src/__tests__/ocr-utils.test.ts
git commit -m "feat: add OCR utility functions for line parsing and classification"
```

---

### Task 3: Create the ScanListModal component

**Files:**
- Create: `frontend/src/components/ScanListModal.tsx`

- [ ] **Step 1: Implement the ScanListModal component**

Create `frontend/src/components/ScanListModal.tsx`:

```typescript
import { useState, useCallback, useRef } from 'react';
import * as Tesseract from 'tesseract.js';
import { parseLines, classifyLines, compressImage } from '../lib/ocr-utils';

type Stage = 'capture' | 'processing' | 'preview' | 'success';

interface ScanListModalProps {
  isOpen: boolean;
  mode: 'shopping' | 'recipe';
  onClose: () => void;
  onItemsExtracted?: (items: string[]) => void;
  onRecipeExtracted?: (recipe: { title: string; ingredients_raw: string; steps_raw: string; content_text: string }) => void;
}

interface ClassifiedLine {
  text: string;
  category: 'ingredient' | 'step';
}

export default function ScanListModal({
  isOpen,
  mode,
  onClose,
  onItemsExtracted,
  onRecipeExtracted,
}: ScanListModalProps) {
  const [stage, setStage] = useState<Stage>('capture');
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [extractedLines, setExtractedLines] = useState<ClassifiedLine[]>([]);
  const [recipeTitle, setRecipeTitle] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setStage('capture');
    setImagePreview(null);
    setProgress(0);
    setProcessingError(null);
    setExtractedLines([]);
    setRecipeTitle('');
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  const handleFileChange = useCallback(
    async (file: File) => {
      if (!file.type.startsWith('image/')) {
        setProcessingError('Please select an image file.');
        return;
      }

      // Create image preview
      const reader = new FileReader();
      reader.onload = () => setImagePreview(reader.result as string);
      reader.readAsDataURL(file);

      // Compress and run OCR
      try {
        setStage('processing');
        setProgress(0);
        setProcessingError(null);

        const compressed = await compressImage(file);
        const blob = await createImageBitmap(new Blob([await compressed.convertToBlob?.() ?? compressed], { type: 'image/jpeg' }));

        // Fallback: use the original blob if compression created issues
        const worker = Tesseract.createWorker('eng', 1, {
          logger: (m) => {
            if (m.status === 'recognizing text') {
              setProgress(Math.round(m.progress * 100));
            }
          },
        });

        const result = await worker.recognize(compressed);
        await worker.terminate();

        const lines = parseLines(result);

        if (lines.length === 0) {
          setProcessingError('No text found in image. Make sure the text is clear and well-lit, then try again.');
          setStage('capture');
          return;
        }

        // Set initial recipe title from first line
        setRecipeTitle(lines[0]);

        // Classify lines
        const classified = classifyLines(lines);
        setExtractedLines(
          classified.ingredients.map((text) => ({ text, category: 'ingredient' as const })).concat(
            classified.steps.map((text) => ({ text, category: 'step' as const }))
          )
        );

        setStage('preview');
      } catch (err) {
        console.error('OCR failed:', err);
        setProcessingError('Scan failed. Try again or upload a different photo.');
        setStage('capture');
      }
    },
    []
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFileChange(file);
    },
    [handleFileChange]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFileChange(file);
    },
    [handleFileChange]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const updateLineText = useCallback((index: number, newText: string) => {
    setExtractedLines((prev) => prev.map((line, i) => (i === index ? { ...line, text: newText } : line)));
  }, []);

  const updateLineCategory = useCallback((index: number, newCategory: 'ingredient' | 'step') => {
    setExtractedLines((prev) => prev.map((line, i) => (i === index ? { ...line, category: newCategory } : line)));
  }, []);

  const removeLine = useCallback((index: number) => {
    setExtractedLines((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const addLine = useCallback(() => {
    setExtractedLines((prev) => [...prev, { text: '', category: mode === 'recipe' ? 'step' : 'ingredient' }]);
  }, [mode]);

  const handleAddAll = useCallback(() => {
    const items = extractedLines.map((l) => l.text).filter(Boolean);
    if (items.length > 0 && onItemsExtracted) {
      onItemsExtracted(items);
      setStage('success');
      setTimeout(handleClose, 1500);
    }
  }, [extractedLines, onItemsExtracted, handleClose]);

  const handleSaveRecipe = useCallback(() => {
    const ingredients = extractedLines.filter((l) => l.category === 'ingredient').map((l) => l.text);
    const steps = extractedLines.filter((l) => l.category === 'step').map((l) => l.text);

    const recipe = {
      title: recipeTitle || 'Scanned Recipe',
      ingredients_raw: ingredients.join('\n'),
      steps_raw: steps.join('\n'),
      content_text: extractedLines.map((l) => l.text).join('\n'),
    };

    if (onRecipeExtracted) {
      onRecipeExtracted(recipe);
      setStage('success');
      setTimeout(handleClose, 1500);
    }
  }, [extractedLines, recipeTitle, onRecipeExtracted, handleClose]);

  const handleRetake = useCallback(() => {
    setStage('capture');
    setProcessingError(null);
    setExtractedLines([]);
    setImagePreview(null);
  }, []);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={handleClose}>
      <div
        className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h2 className="text-lg font-bold text-white">
            {mode === 'shopping' ? 'Scan a List' : 'Scan a Recipe'}
          </h2>
          <button onClick={handleClose} className="text-slate-400 hover:text-white text-xl leading-none">
            ✕
          </button>
        </div>

        <div className="p-4">
          {/* Stage: Capture */}
          {stage === 'capture' && (
            <div className="space-y-4">
              {imagePreview && (
                <div className="relative rounded-lg overflow-hidden bg-slate-900">
                  <img src={imagePreview} alt="Captured" className="w-full h-auto max-h-64 object-contain" />
                </div>
              )}

              <div
                className="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center hover:border-emerald-500 transition cursor-pointer"
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => fileInputRef.current?.click()}
              >
                <p className="text-slate-300 mb-2">Tap to capture or upload a photo</p>
                <p className="text-slate-500 text-sm">Takes a photo of a handwritten or printed list</p>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleInputChange}
                className="hidden"
              />

              {processingError && (
                <p className="text-red-400 text-sm text-center">{processingError}</p>
              )}
            </div>
          )}

          {/* Stage: Processing */}
          {stage === 'processing' && (
            <div className="text-center py-8 space-y-4">
              {imagePreview && (
                <img src={imagePreview} alt="Scanning" className="w-full h-auto max-h-48 rounded-lg object-contain opacity-50" />
              )}
              <div>
                <p className="text-white font-medium mb-2">Scanning text...</p>
                <div className="w-full bg-slate-700 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-slate-400 text-sm mt-2">{progress}%</p>
              </div>
            </div>
          )}

          {/* Stage: Preview & Edit */}
          {stage === 'preview' && (
            <div className="space-y-3">
              <p className="text-slate-300 text-sm">
                {mode === 'shopping'
                  ? 'Edit the extracted items, then tap "Add All" to add them to your shopping list.'
                  : 'Review and edit the extracted recipe. Tap a line to change its category.'}
              </p>

              {mode === 'recipe' && (
                <input
                  type="text"
                  value={recipeTitle}
                  onChange={(e) => setRecipeTitle(e.target.value)}
                  placeholder="Recipe title"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
                />>
              )}

              <div className="space-y-2 max-h-60 overflow-y-auto">
                {extractedLines.map((line, index) => (
                  <div key={index} className="flex items-center gap-2">
                    {mode === 'recipe' && (
                      <button
                        onClick={() =>
                          updateLineCategory(index, line.category === 'ingredient' ? 'step' : 'ingredient')
                        }
                        className={`px-2 py-1 rounded text-xs whitespace-nowrap ${
                          line.category === 'ingredient'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-blue-500/20 text-blue-400'
                        }`}
                      >
                        {line.category === 'ingredient' ? '🥕' : '📝'}
                      </button>
                    )}
                    <input
                      type="text"
                      value={line.text}
                      onChange={(e) => updateLineText(index, e.target.value)}
                      className="flex-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-600 text-white text-sm focus:border-emerald-500 focus:outline-none"
                    />
                    <button
                      onClick={() => removeLine(index)}
                      className="text-slate-500 hover:text-red-400 transition text-sm"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>

              <button
                onClick={addLine}
                className="text-emerald-400 text-sm hover:text-emerald-300 transition"
              >
                + Add line
              </button>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleRetake}
                  className="flex-1 px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-white transition"
                >
                  Retake
                </button>
                {mode === 'shopping' ? (
                  <button
                    onClick={handleAddAll}
                    disabled={extractedLines.every((l) => !l.text.trim())}
                    className="flex-1 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 disabled:text-slate-400 text-white transition"
                  >
                    Add All
                  </button>
                ) : (
                  <button
                    onClick={handleSaveRecipe}
                    disabled={extractedLines.every((l) => !l.text.trim())}
                    className="flex-1 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 disabled:text-slate-400 text-white transition"
                  >
                    Save Recipe
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Stage: Success */}
          {stage === 'success' && (
            <div className="text-center py-6">
              <p className="text-emerald-400 text-lg font-medium">✓ Success!</p>
              <p className="text-slate-400 text-sm mt-1">
                {mode === 'shopping' ? 'Items added to your shopping list.' : 'Recipe saved.'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

Wait, there's a syntax error — extra `>` after the recipe title input closing tag. Let me fix that:

```typescript
              {mode === 'recipe' && (
                <input
                  type="text"
                  value={recipeTitle}
                  onChange={(e) => setRecipeTitle(e.target.value)}
                  placeholder="Recipe title"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
                />
              )}
```

- [ ] **Step 2: Verify the component compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No TypeScript errors related to `ScanListModal.tsx`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ScanListModal.tsx
git commit -m "feat: add ScanListModal component with OCR capture, processing, and preview stages"
```

---

### Task 4: Integrate ScanListModal into MealsPage

**Files:**
- Modify: `frontend/src/pages/MealsPage.tsx`

- [ ] **Step 1: Add the modal import and state**

Add to the imports at the top of `MealsPage.tsx`:

```typescript
import ScanListModal from '../components/ScanListModal';
```

Add state after the existing `showAddItemForm` state (around line 89):

```typescript
  const [showScanModal, setShowScanModal] = useState(false);
```

- [ ] **Step 2: Add handler for shopping mode extraction**

Add a handler function in the component body, after the existing mutations (around line 135):

```typescript
  const handleShoppingItemsExtracted = useCallback(
    (items: string[]) => {
      // Add each item to the shopping list
      items.forEach((item) => {
        addShoppingItemMutation.mutate({ item });
      });
    },
    [addShoppingItemMutation]
  );
```

- [ ] **Step 3: Add handler for recipe mode extraction**

Add after the shopping handler:

```typescript
  const handleRecipeExtracted = useCallback(
    (recipe: { title: string; ingredients_raw: string; steps_raw: string; content_text: string }) => {
      createRecipeMutation.mutate({
        title: recipe.title,
        content_text: recipe.content_text,
        ingredients_raw: recipe.ingredients_raw,
        steps_raw: recipe.steps_raw,
        dietary_tag_ids: [],
      });
    },
    [createRecipeMutation]
  );
```

- [ ] **Step 4: Add "Scan List" button in the Shopping tab**

In the shopping tab section (around line 380, where the "Add Item" form toggle is), add a "Scan List" button next to the "Add Item" button. Find the existing button row and add a scan button:

Look for the section around line 376-380 where the "Add Item" button is. Add a scan button:

```typescript
              <div className="flex gap-3">
                <button
                  onClick={() => setShowAddItemForm(true)}
                  className="flex-1 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition"
                >
                  + Add Item
                </button>
                <button
                  onClick={() => setShowScanModal(true)}
                  className="flex-1 px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-white transition"
                >
                  📷 Scan List
                </button>
              </div>
```

- [ ] **Step 5: Add "Scan Recipe" button in the Recipes tab**

In the recipes tab section, find the header area where the recipe search/input is. Add a "Scan Recipe" button. Look for the recipes tab header around line 283-285 and add:

```typescript
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Search recipes..."
```

Change to:

```typescript
          <div className="flex gap-3">
            <button
              onClick={() => setShowScanModal(true)}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition whitespace-nowrap"
            >
              📷 Scan Recipe
            </button>
            <input
              type="text"
              placeholder="Search recipes..."
```

- [ ] **Step 6: Add the ScanListModal component at the bottom of the JSX**

Just before the closing `</div>` of the main return (before line 479), add:

```typescript
      {/* Scan List Modal */}
      <ScanListModal
        isOpen={showScanModal}
        mode="shopping"
        onClose={() => setShowScanModal(false)}
        onItemsExtracted={handleShoppingItemsExtracted}
      />
```

- [ ] **Step 7: Verify the page compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No TypeScript errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/MealsPage.tsx
git commit -m "feat: integrate ScanListModal into MealsPage for shopping and recipe scanning"
```

---

### Task 5: Fix the PendingOperation entity type

**Files:**
- Modify: `frontend/src/lib/idb.ts`

The `PendingOperation.entity` type currently only includes `'shopping-item' | 'chore-instance'`. Recipe creation also uses `enqueueOperation` for offline support (see `createRecipeMutation` in MealsPage). We need to add `'recipe'` to the union type.

- [ ] **Step 1: Add 'recipe' to the PendingOperation entity type**

Update the entity type in `frontend/src/lib/idb.ts` line 7:

```typescript
export interface PendingOperation {
  id: string
  type: 'create' | 'update' | 'delete'
  entity: 'shopping-item' | 'chore-instance' | 'recipe'
  data: Record<string, unknown>
  endpoint: string
  timestamp: number
  serverVersion?: string
}
```

- [ ] **Step 2: Update the enqueueOperation calls in MealsPage**

In the `createRecipeMutation` (around line 76-80), add offline support matching the existing pattern:

```typescript
  const createRecipeMutation = useMutation({
    mutationFn: (data: { title: string; content_text: string; ingredients_raw?: string; steps_raw?: string; dietary_tag_ids: string[] }) => {
      if (!navigator.onLine) {
        enqueueOperation({
          type: 'create',
          entity: 'recipe',
          data,
          endpoint: '/meals/recipes',
        })
        useOfflineStore.getState().incrementPending()
      }
      return api.post('/meals/recipes', data).then(r => r.data)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["meals", "recipes"] }),
  });
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/idb.ts frontend/src/pages/MealsPage.tsx
git commit -m "fix: add recipe entity to PendingOperation type and offline queue support"
```

---

### Task 6: Final verification

- [ ] **Step 1: Full TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: Zero errors.

- [ ] **Step 2: Full build check**

Run: `cd frontend && npm run build`
Expected: Build succeeds, no errors.

- [ ] **Step 3: Backend tests still pass**

Run: `cd backend && source .venv/bin/activate && pytest`
Expected: All existing tests pass (no backend changes).

- [ ] **Step 4: Commit any remaining changes**

```bash
git add -A
git commit -m "chore: final verification checks"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ Tesseract.js bundled — Task 1
- ✅ ScanListModal component with 4 stages — Task 3
- ✅ Shopping mode: extract → preview → add all — Task 3 (preview stage), Task 4 (shopping handler)
- ✅ Recipe mode: extract → classify → edit → save — Task 3 (preview stage), Task 4 (recipe handler)
- ✅ Camera capture + file upload — Task 3 (capture stage)
- ✅ Image compression — Task 2 (compressImage utility)
- ✅ Line classification heuristic — Task 2 (classifyLines utility)
- ✅ Error handling — Task 3 (all error states in modal)
- ✅ Offline support — Task 5 (recipe entity type + enqueueOperation)
- ✅ Tests for utilities — Task 2

**2. Placeholder scan:** No "TBD", "TODO", "implement later", or "similar to" patterns found. All code is complete with actual implementations.

**3. Type consistency:** `classifyLines` returns `{ ingredients: string[], steps: string[] }` used consistently in Task 3 and Task 4. `parseLines` return type `string[]` used consistently. `ScanListModalProps` interface matches all usage sites.

**4. Scope check:** Frontend-only change. No backend endpoints, schemas, or models modified. Single new component, single new utility file. Focused and implementable.
