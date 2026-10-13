import { useState } from 'react'
import { errorDetail } from '../api/client'
import { useDeleteMedia, useMedia, useUploadMedia, type MediaItem } from '../api/media'
import { canCreateEvents } from '../lib/permissions'
import { useAuthStore } from '../stores/auth'

function duration(seconds: number): string {
  const s = Math.round(seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** The family's photos and videos, shown by the wall when it's idle. */
export default function PhotosPage() {
  const user = useAuthStore((s) => s.user)
  const { data: items = [], isLoading } = useMedia()
  const upload = useUploadMedia()
  const remove = useDeleteMedia()
  const [uploading, setUploading] = useState<string | null>(null)
  const [failures, setFailures] = useState<string[]>([])
  const canUpload = canCreateEvents(user) // admins and members
  const canRemove = (item: MediaItem) => user?.role === 'admin' || (!!user && item.uploaded_by === user.id)

  const addFiles = async (files: File[]) => {
    setFailures([])
    // One at a time: a family server converts videos one by one anyway.
    for (const file of files) {
      setUploading(file.name)
      try {
        await upload.mutateAsync(file)
      } catch (err) {
        setFailures((f) => [...f, `${file.name}: ${errorDetail(err, 'Could not add it')}`])
      }
    }
    setUploading(null)
  }

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-white">Photos &amp; videos</h1>
            <p className="text-sm text-gray-400">Shown on the wall when nobody is using it. Location data is removed.</p>
          </div>
          {canUpload && (
            <label className="cursor-pointer rounded-lg bg-primary px-4 py-2 font-medium text-white hover:bg-primary-dark">
              {uploading ? `Adding ${uploading}…` : 'Add photos or videos'}
              <input
                type="file"
                multiple
                accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/webm"
                className="sr-only"
                aria-label="Add photos or videos"
                disabled={!!uploading}
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? [])
                  e.target.value = ''
                  if (files.length) void addFiles(files)
                }}
              />
            </label>
          )}
        </div>

        {failures.length > 0 && (
          <ul className="mb-4 space-y-1 rounded bg-red-900/50 px-4 py-2 text-sm text-red-300">
            {failures.map((f) => <li key={f}>{f}</li>)}
          </ul>
        )}

        {!isLoading && items.length === 0 && (
          <p className="text-gray-400">No photos or videos yet.{canUpload ? ' Add some and they will show on the wall.' : ''}</p>
        )}

        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((item) => (
            <li key={item.id} className="group relative overflow-hidden rounded-lg border border-gray-800 bg-gray-900">
              <div className="flex aspect-[4/3] items-center justify-center bg-black">
                {item.status === 'ready' ? (
                  <img src={item.thumb_url} alt={item.original_name} className="h-full w-full object-cover" loading="lazy" />
                ) : item.status === 'processing' ? (
                  <span className="text-sm text-gray-400">Converting…</span>
                ) : (
                  <span className="px-3 text-center text-xs text-red-300">Couldn't add: {item.error}</span>
                )}
              </div>
              <div className="flex items-center justify-between gap-2 px-2 py-1.5 text-xs text-gray-400">
                <span className="truncate">{item.original_name}</span>
                {item.kind === 'video' && item.duration_s != null && <span>{duration(item.duration_s)}</span>}
              </div>
              {canRemove(item) && (
                <button
                  onClick={() => {
                    if (confirm(`Remove ${item.original_name}? It will stop showing on the wall.`)) remove.mutate(item.id)
                  }}
                  className="absolute right-1.5 top-1.5 rounded bg-black/70 px-2 py-0.5 text-xs text-white opacity-80 hover:opacity-100"
                  aria-label={`Remove ${item.original_name}`}
                >
                  ✕
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
