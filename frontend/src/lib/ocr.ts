/**
 * Read the text in a photo, on this device (Phase 10). tesseract.js runs in
 * a Web Worker; the photo never leaves the phone. Its engine, worker and
 * English data are served by OpenFamHub itself from /ocr/ (copied there from
 * node_modules by scripts/ocr-assets.mjs at build time), so nothing is
 * fetched from a CDN and scanning works on a LAN without internet. The
 * library loads only when someone scans.
 */
export const OCR_PATHS = {
  workerPath: '/ocr/worker.min.js',
  corePath: '/ocr',   // a folder: tesseract picks the build this browser supports
  langPath: '/ocr',   // eng.traineddata.gz
} as const

export interface OcrProgress {
  status: string
  progress: number  // 0–1 within the current status
}

/** Friendlier words for tesseract's progress steps. */
export function progressLabel(p: OcrProgress | null): string {
  if (!p) return 'Starting…'
  if (p.status.startsWith('loading') || p.status.startsWith('initializ')) return 'Getting ready…'
  if (p.status.startsWith('recognizing')) return `Reading… ${Math.round(p.progress * 100)}%`
  return 'Working…'
}

/** `paths` is for tests, which run the real engine in Node from node_modules. */
export async function readText(image: Blob | string, onProgress?: (p: OcrProgress) => void,
  paths: Record<string, string> = OCR_PATHS): Promise<string> {
  const { createWorker, OEM } = await import('tesseract.js')
  const worker = await createWorker('eng', OEM.LSTM_ONLY, {
    ...paths,
    logger: (m: { status: string; progress: number }) => onProgress?.({ status: m.status, progress: m.progress }),
  })
  try {
    const { data } = await worker.recognize(image)
    return data.text
  } finally {
    await worker.terminate()
  }
}
