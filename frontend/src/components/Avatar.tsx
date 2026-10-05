import { cn } from '../lib/utils'

interface AvatarProps {
  name: string
  color: string
  emoji?: string | null
  className?: string
}

/** Emoji avatar on the member's color, or their initial when no emoji is set. */
export default function Avatar({ name, color, emoji, className }: AvatarProps) {
  return (
    <span
      className={cn('inline-flex items-center justify-center rounded-full font-bold text-white', className)}
      style={{ backgroundColor: color || '#4F46E5' }}
      aria-hidden="true"
    >
      {emoji || name.charAt(0).toUpperCase()}
    </span>
  )
}
