interface WallPhotoPlaceholderProps {
  fullscreen: boolean
}

export default function WallPhotoPlaceholder({ fullscreen }: WallPhotoPlaceholderProps) {
  return (
    <div
      className={`flex items-center justify-center bg-slate-900 ${fullscreen ? 'fixed inset-0 z-50' : ''}`}
    >
      <span className="text-4xl font-light tracking-widest text-slate-600">
        OpenFamHub
      </span>
    </div>
  )
}
