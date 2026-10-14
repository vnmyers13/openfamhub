// Copy tesseract.js's worker, LSTM engine builds and English data into
// public/ocr/, so the app serves them itself (lib/ocr.ts). Runs before
// `npm run dev` and `npm run build`; public/ocr/ is not committed.
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const nm = join(root, 'node_modules')
const out = join(root, 'public', 'ocr')
const files = [
  ['tesseract.js/dist/worker.min.js', 'worker.min.js'],
  // LSTM-only builds (OEM.LSTM_ONLY): plain, SIMD and relaxed-SIMD.
  ['tesseract.js-core/tesseract-core-lstm.wasm.js', 'tesseract-core-lstm.wasm.js'],
  ['tesseract.js-core/tesseract-core-simd-lstm.wasm.js', 'tesseract-core-simd-lstm.wasm.js'],
  ['tesseract.js-core/tesseract-core-relaxedsimd-lstm.wasm.js', 'tesseract-core-relaxedsimd-lstm.wasm.js'],
  // The compact "best_int" English model (2.9 MB), made for the LSTM engine.
  ['@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz', 'eng.traineddata.gz'],
]

mkdirSync(out, { recursive: true })
for (const [from, to] of files) {
  const src = join(nm, from)
  if (!existsSync(src)) {
    console.error(`ocr-assets: missing ${from}; run npm install`)
    process.exit(1)
  }
  copyFileSync(src, join(out, to))
}
console.log(`ocr-assets: ${files.length} files in public/ocr/`)
