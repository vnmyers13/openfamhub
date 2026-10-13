import { useWallProgress } from '../api/wall'
import FamilyProgress from '../components/FamilyProgress'

/** The wall's family panel: everyone's stars, streaks and badges, live. */
export default function WallProgress() {
  const { data } = useWallProgress()
  if (!data) return null
  return <FamilyProgress rows={data} size="wall" />
}
