# OCR List Scanner — Design Spec

## Overview

Add client-side OCR to extract text from photos of handwritten or printed lists. When used from the Shopping List tab, extracted items are added to the weekly shopping list. When used from the Recipes tab, extracted text is parsed into a new recipe (title, ingredients, steps).

## Architecture

Frontend-only change. No backend endpoints, schemas, or models are modified.

- **Package**: `tesseract.js` added to `frontend/package.json`
- **Component**: `ScanListModal.tsx` — shared modal used from both tabs
- **Engine**: Tesseract.js runs in a Web Worker, language data cached by browser (~6MB)

## Components

### ScanListModal

Single shared component with 4 stages:

1. **Capture** — Camera button (`<input accept="image/*" capture="environment">`) + file upload drop zone. Image preview shown.
2. **Processing** — Progress bar driven by Tesseract progress callback.
3. **Preview & Edit** — Extracted text as editable lines. Mode-dependent layout:
   - **Shopping mode**: Each line = one item. Edit/add/remove lines. "Add All" submits via existing `POST /meals/shopping-list`.
   - **Recipe mode**: First non-empty line = title. Remaining lines classified into ingredients vs steps via heuristic (lines matching quantity+unit patterns flagged as ingredients). User can re-categorize. "Save Recipe" submits via existing `POST /meals/recipes`.
4. **Confirmation** — Success toast, modal closes.

Props:

```typescript
interface ScanListModalProps {
  isOpen: boolean;
  mode: "shopping" | "recipe";
  onClose: () => void;
  onItemsExtracted?: (items: string[]) => void;  // shopping mode
  onRecipeExtracted?: (recipe: { title: string; ingredients_raw: string; steps_raw: string; content_text: string }) => void;  // recipe mode
}
```

## Data Flow

### Shopping List Mode

1. User captures/uploads image → `File` object
2. Image auto-compressed to max 1920px width
3. `Tesseract.recognize(image, 'eng')` in Web Worker
4. `result.lines.map(line => line.text.trim()).filter(Boolean)` → extracted lines
5. Lines rendered as editable inputs in modal preview
6. "Add All" → loops lines, calls `addShoppingItemMutation.mutate({ item })` for each
7. Offline: items queued via existing `enqueueOperation`

### Recipe Mode

1. Same OCR flow
2. First non-empty line → recipe title
3. Remaining lines classified: lines matching ingredient patterns (`tbsp`, `cup`, `oz`, `g`, `kg`, `large`, `small`, `pinch`, `dash`, `slice`, `clove`, `can`, `lb`, `package`) → ingredients; rest → steps
4. User can re-categorize by tapping toggle on each line
5. "Save Recipe" → calls `createRecipeMutation.mutate({ title, ingredients_raw, steps_raw, content_text, dietary_tag_ids: [] })`
6. Offline: queued via `enqueueOperation`

### OCR Engine

- Single `Tesseract.createWorker('eng', 1, { logger })` instance, cached and reused
- Progress callback drives UI percentage
- Language data loaded once, cached by browser

## Error Handling

- **OCR failure** (worker crash/network): "Scan failed. Try again or upload a different photo." with retry button.
- **Empty extraction**: "No text found in image. Make sure the text is clear and well-lit."
- **API failure** (batch add/save): Per-item errors shown. Offline items queued with "Syncing..." indicator.
- **Large image**: Auto-compress to max 1920px width before OCR.
- **Unsupported browser**: "OCR requires a modern browser. Use Chrome, Safari, or Firefox."

## Testing

- **Unit**: `parseLines()` utility — extract and trim text lines from Tesseract result
- **Unit**: `classifyLines()` — ingredient vs step detection heuristic with various input formats
- **Integration**: Mock Tesseract returning known text → verify items/recipe created correctly

## UI Integration

### MealsPage — Shopping List Tab

Add "Scan List" button next to "Add Item" button. Opens `ScanListModal` with `mode="shopping"`. On `onItemsExtracted`, iterates and adds each item.

### MealsPage — Recipes Tab

Add "Scan Recipe" button in the recipes tab header area. Opens `ScanListModal` with `mode="recipe"`. On `onRecipeExtracted`, calls `createRecipeMutation`.
