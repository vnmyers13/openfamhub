import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import { buildLabel, visibleCommit } from '../lib/buildInfo'
import { cn } from '../lib/utils'

type HealthResponse = {
  version?: string
  build?: string
  commit?: string | null
}

type BuildInfoBadgeProps = {
  className?: string
}

// Set at image build time (deploy.sh publish/deploy -> OPENFAMHUB_BUILD, e.g. 0.54).
const APP_BUILD = (import.meta.env.VITE_APP_BUILD as string | undefined) || 'dev'

export default function BuildInfoBadge({ className }: BuildInfoBadgeProps) {
  const { data: health } = useQuery({
    queryKey: ['api-health'],
    queryFn: async () => (await apiClient.get('/health')).data as HealthResponse,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
  const publishedBuild = buildLabel({
    apiBuild: health?.build,
    apiVersion: health?.version,
    fallbackBuild: APP_BUILD,
  })
  const commit = visibleCommit(health?.commit)

  return (
    <div className={cn('rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-[11px] text-slate-500', className)}>
      <p className="font-semibold uppercase tracking-wider text-slate-600">Help &amp; About</p>
      <p className="mt-1 text-slate-400">OpenFamHub {publishedBuild}</p>
      {commit && <p className="font-mono text-[10px] text-slate-600">{commit}</p>}
    </div>
  )
}
