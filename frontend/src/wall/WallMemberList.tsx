import { useWallMembers } from '../api/wall'

export default function WallMemberList() {
  const { data: members = [] } = useWallMembers()

  return (
    <div className="flex flex-col gap-3">
      {members.map((m) => (
        <div key={m.id} className="flex items-center gap-3">
          <span
            className="inline-block h-5 w-5 rounded-full"
            style={{ backgroundColor: m.color_hex || '#6366f1' }}
          />
          <span className="text-lg text-slate-300">{m.display_name}</span>
        </div>
      ))}
    </div>
  )
}
