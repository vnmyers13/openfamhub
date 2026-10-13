import { useEffect, useMemo, useReducer } from 'react'
import { useWallMedia, type WallMediaItem } from '../api/wall'
import { ShuffleBag } from '../lib/shuffle'
import WallPhotoPlaceholder from './WallPhotoPlaceholder'

export const PHOTO_MS = 12_000

type Slide = { id: string | null; step: number }

interface Props {
  photoMs?: number
  random?: () => number
}

/**
 * The idle screen: the family's photos and videos, full screen, in shuffled
 * order with every item shown once before any repeats. Photos stay up for
 * `photoMs`; videos play muted to the end. With no media it shows the logo.
 */
export default function WallSlideshow({ photoMs = PHOTO_MS, random }: Props) {
  const { data: items = [] } = useWallMedia()
  const bag = useMemo(() => new ShuffleBag<string>([], random), [random])
  const ids = items.map((i) => i.id).join(',')

  // `step` changes on every advance so a single repeating item still restarts.
  const [slide, advance] = useReducer(
    (prev: Slide): Slide => ({ id: bag.next(), step: prev.step + 1 }),
    { id: null, step: 0 },
  )

  useEffect(() => {
    bag.update(ids ? ids.split(',') : [])
    advance()
  }, [bag, ids])

  const current: WallMediaItem | undefined = items.find((i) => i.id === slide.id)

  useEffect(() => {
    if (!current) return
    // Photos advance on a timer; videos on "ended", with a backstop in case it never fires.
    const ms = current.kind === 'photo' ? photoMs : ((current.duration_s ?? 60) + 5) * 1000
    const timer = setTimeout(advance, ms)
    return () => clearTimeout(timer)
  }, [current, slide.step, photoMs])

  if (!current) return <WallPhotoPlaceholder fullscreen />

  const fill = 'fixed inset-0 z-50 h-full w-full bg-black object-contain'
  return current.kind === 'video' ? (
    <video
      key={`${current.id}-${slide.step}`}
      className={fill}
      src={current.wall_url}
      autoPlay
      muted
      playsInline
      onEnded={advance}
      onError={advance}
      data-testid="wall-slide"
    />
  ) : (
    <img key={`${current.id}-${slide.step}`} className={fill} src={current.wall_url} alt="" data-testid="wall-slide" />
  )
}
