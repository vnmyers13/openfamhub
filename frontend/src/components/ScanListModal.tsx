import { useState, useRef, useCallback } from 'react'
import * as Tesseract from 'tesseract.js'
import { parseLines, classifyLines, compressImage, bitmapToBlob } from '../lib/ocr-utils'

interface ScanListModalProps {
  isOpen: boolean
  mode: 'shopping' | 'recipe'
  onClose: () => void
  onItemsExtracted?: (items: string[]) => void
  onRecipeExtracted?: (recipe: { title: string; ingredients_raw: string; steps_raw: string; content_text: string }) => void
}

type Stage = 'capture' | 'processing' | 'preview' | 'success'

interface ClassifiedLine {
  text: string
  category: 'ingredient' | 'step'
}

export function ScanListModal({
  isOpen,
  mode,
  onClose,
  onItemsExtracted,
  onRecipeExtracted,
}: ScanListModalProps) {
  const [stage, setStage] = useState<Stage>('capture')
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [processingError, setProcessingError] = useState<string | null>(null)
  const [extractedLines, setExtractedLines] = useState<ClassifiedLine[]>([])
  const [recipeTitle, setRecipeTitle] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const headerTitle = mode === 'shopping' ? 'Scan a List' : 'Scan a Recipe'

  const handleFileSelect = useCallback((file: File) => {
    if (!file.type.startsWith('image/')) {
      setProcessingError('Please select an image file')
      return
    }

    const reader = new FileReader()
    reader.onload = (e) => {
      setImagePreview(e.target?.result as string)
    }
    reader.readAsDataURL(file)
  }, [])

  const startOCR = useCallback(async (file: File) => {
    setStage('processing')
    setProgress(0)
    setProcessingError(null)

    try {
      const worker = await Tesseract.createWorker('eng', 1, {
        logger: (m) => {
          if (m.status === 'recognizing text') {
            setProgress(Math.round(m.progress * 100))
          }
        },
      })
      const compressed = await compressImage(file)
      const blob = await bitmapToBlob(compressed)
      const result = await worker.recognize(blob)
      await worker.terminate()

      const lines = parseLines(result)

      if (lines.length === 0) {
        setProcessingError('No text found in image')
        setStage('capture')
        return
      }

      const classified = classifyLines(lines)
      const classifiedWithCategory: ClassifiedLine[] = lines.map((line) => ({
        text: line,
        category: classified.ingredients.includes(line) ? 'ingredient' : 'step',
      }))

      setExtractedLines(classifiedWithCategory)
      const titleLine = lines.find((line) => !classified.ingredients.includes(line)) ?? lines[0]
      setRecipeTitle(titleLine)
      setStage('preview')
    } catch {
      setProcessingError('Scan failed')
      setStage('capture')
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setProcessingError(null)
    const file = e.dataTransfer.files[0]
    if (file) {
      handleFileSelect(file)
      startOCR(file)
    }
  }, [handleFileSelect, startOCR])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      handleFileSelect(file)
      startOCR(file)
    }
  }, [handleFileSelect, startOCR])

  const handleRetake = useCallback(() => {
    setStage('capture')
    setImagePreview(null)
    setProgress(0)
    setProcessingError(null)
    setExtractedLines([])
    setRecipeTitle('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [])

  const handleToggleCategory = useCallback((index: number) => {
    setExtractedLines((prev) =>
      prev.map((line, i) =>
        i === index
          ? { ...line, category: line.category === 'ingredient' ? 'step' : 'ingredient' }
          : line
      )
    )
  }, [])

  const handleLineChange = useCallback((index: number, newText: string) => {
    setExtractedLines((prev) =>
      prev.map((line, i) => (i === index ? { ...line, text: newText } : line))
    )
  }, [])

  const handleRemoveLine = useCallback((index: number) => {
    setExtractedLines((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const handleAddLine = useCallback(() => {
    setExtractedLines((prev) => [...prev, { text: '', category: mode === 'recipe' ? 'step' : 'ingredient' }])
  }, [mode])

  const handleSubmit = useCallback(() => {
    if (mode === 'shopping') {
      const items = extractedLines.map((l) => l.text).filter((t) => t.trim().length > 0)
      if (items.length > 0 && onItemsExtracted) {
        onItemsExtracted(items)
      }
    } else {
      const ingredients = extractedLines.filter((l) => l.category === 'ingredient').map((l) => l.text)
      const steps = extractedLines.filter((l) => l.category === 'step').map((l) => l.text)
      const contentText = extractedLines.map((l) => l.text).join('\n')
      if (onRecipeExtracted) {
        onRecipeExtracted({
          title: recipeTitle,
          ingredients_raw: ingredients.join('\n'),
          steps_raw: steps.join('\n'),
          content_text: contentText,
        })
      }
    }
    setStage('success')
    setTimeout(() => {
      onClose()
      setStage('capture')
      setImagePreview(null)
      setProgress(0)
      setProcessingError(null)
      setExtractedLines([])
      setRecipeTitle('')
    }, 1500)
  }, [mode, extractedLines, recipeTitle, onItemsExtracted, onRecipeExtracted, onClose])

  const allLinesEmpty = extractedLines.length > 0 && extractedLines.every((l) => !l.text.trim())

  if (!isOpen) return null

  const captureInstructions = mode === 'shopping'
    ? 'Take a photo or upload an image of your shopping list'
    : 'Take a photo or upload an image of a recipe'

  const previewInstructions = mode === 'shopping'
    ? 'Review and edit your extracted items below:'
    : 'Review and edit your extracted recipe below:'

  const submitLabel = mode === 'shopping' ? 'Add All' : 'Save Recipe'

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl border border-slate-700 w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h2 className="text-xl font-bold text-white">{headerTitle}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition p-1"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {stage === 'capture' && (
            <div>
              <p className="text-gray-400 text-sm mb-4 text-center">{captureInstructions}</p>
              <div
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                className="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center cursor-pointer hover:border-emerald-500 hover:bg-slate-700/50 transition"
              >
                <div className="text-gray-400 mb-2">
                  <svg className="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <p className="text-sm">Drop an image here or click to browse</p>
                </div>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleInputChange}
                className="hidden"
              />
              {imagePreview && (
                <div className="mt-4">
                  <img src={imagePreview} alt="Preview" className="w-full rounded-lg" />
                </div>
              )}
              {processingError && (
                <p className="text-red-400 text-sm mt-3 text-center">{processingError}</p>
              )}
            </div>
          )}

          {stage === 'processing' && (
            <div>
              {imagePreview && (
                <img src={imagePreview} alt="Processing" className="w-full rounded-lg opacity-50 mb-4" />
              )}
              <div className="text-center">
                <p className="text-white text-lg mb-3">Scanning...</p>
                <div className="w-full bg-slate-700 rounded-full h-3 mb-2">
                  <div
                    className="bg-emerald-600 h-3 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-gray-400 text-sm">{progress}%</p>
              </div>
              {processingError && (
                <p className="text-red-400 text-sm mt-3 text-center">{processingError}</p>
              )}
            </div>
          )}

          {stage === 'preview' && (
            <div>
              <p className="text-gray-400 text-sm mb-4">{previewInstructions}</p>

              {mode === 'recipe' && (
                <div className="mb-4">
                  <label className="block text-sm text-gray-400 mb-1">Recipe Title</label>
                  <input
                    type="text"
                    value={recipeTitle}
                    onChange={(e) => setRecipeTitle(e.target.value)}
                    className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-emerald-500 focus:outline-none text-white"
                  />
                </div>
              )}

              <div className="space-y-2 mb-4">
                {extractedLines.map((line, index) => (
                  <div key={index} className="flex gap-2 items-center">
                    {mode === 'recipe' && (
                      <button
                        onClick={() => handleToggleCategory(index)}
                        className={`px-2 py-2 rounded-lg text-sm transition flex-shrink-0 ${
                          line.category === 'ingredient'
                            ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30'
                            : 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                        }`}
                      >
                        {line.category === 'ingredient' ? '🥕' : '📝'}
                      </button>
                    )}
                    <input
                      type="text"
                      value={line.text}
                      onChange={(e) => handleLineChange(index, e.target.value)}
                      className="flex-1 p-2 rounded-lg bg-white/5 border border-white/20 focus:border-emerald-500 focus:outline-none text-white text-sm"
                    />
                    <button
                      onClick={() => handleRemoveLine(index)}
                      className="text-gray-500 hover:text-red-400 transition p-2 flex-shrink-0"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>

              <button
                onClick={handleAddLine}
                className="text-emerald-400 text-sm hover:text-emerald-300 transition mb-4"
              >
                + Add line
              </button>
            </div>
          )}

          {stage === 'success' && (
            <div className="text-center py-8">
              <p className="text-2xl text-emerald-400 font-bold">✓ Success!</p>
            </div>
          )}
        </div>

        {(stage === 'preview' || stage === 'success') && (
          <div className="flex gap-3 p-4 border-t border-slate-700">
            <button
              onClick={handleRetake}
              className="flex-1 px-4 py-2 rounded-lg bg-white/5 border border-white/20 text-gray-400 hover:text-white hover:bg-white/10 transition"
            >
              Retake
            </button>
            {stage === 'preview' && (
              <button
                onClick={handleSubmit}
                disabled={allLinesEmpty}
                className="flex-1 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {submitLabel}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
