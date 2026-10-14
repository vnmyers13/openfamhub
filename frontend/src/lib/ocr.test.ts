import { afterEach, describe, expect, it, vi } from 'vitest'

const terminate = vi.fn(async () => {})
const recognize = vi.fn()
const createWorker = vi.fn()
vi.mock('tesseract.js', () => ({ OEM: { LSTM_ONLY: 1 }, createWorker }))

import { OCR_PATHS, progressLabel, readText } from './ocr'

describe('readText (browser setup)', () => {
  afterEach(() => vi.clearAllMocks())

  it('loads everything from /ocr/ on this server, reports progress, and closes the worker', async () => {
    createWorker.mockImplementation(async (_lang, _oem, opts: { logger: (m: unknown) => void }) => {
      opts.logger({ status: 'recognizing text', progress: 0.5 })
      return { recognize, terminate }
    })
    recognize.mockResolvedValue({ data: { text: 'Milk\n' } })
    const progress = vi.fn()
    expect(await readText(new Blob(['x']), progress)).toBe('Milk\n')
    const [lang, oem, opts] = createWorker.mock.calls[0]
    expect([lang, oem]).toEqual(['eng', 1])
    expect(opts).toMatchObject({ workerPath: '/ocr/worker.min.js', corePath: '/ocr', langPath: '/ocr' })
    expect(Object.values(OCR_PATHS).every((p) => p.startsWith('/ocr'))).toBe(true)  // never a CDN
    expect(progress).toHaveBeenCalledWith({ status: 'recognizing text', progress: 0.5 })
    expect(terminate).toHaveBeenCalledOnce()
  })

  it('closes the worker when reading fails too', async () => {
    createWorker.mockResolvedValue({ recognize, terminate })
    recognize.mockRejectedValue(new Error('bad image'))
    await expect(readText(new Blob(['x']))).rejects.toThrow('bad image')
    expect(terminate).toHaveBeenCalledOnce()
  })

  it('says what is happening in plain words', () => {
    expect(progressLabel(null)).toBe('Starting…')
    expect(progressLabel({ status: 'loading language traineddata', progress: 0.3 })).toBe('Getting ready…')
    expect(progressLabel({ status: 'recognizing text', progress: 0.42 })).toBe('Reading… 42%')
    expect(progressLabel({ status: 'something else', progress: 0 })).toBe('Working…')
  })
})
