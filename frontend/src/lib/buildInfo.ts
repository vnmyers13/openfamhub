export type BuildInfo = {
  apiBuild?: string | null
  apiVersion?: string | null
  fallbackBuild: string
}

function meaningful(value?: string | null): string | null {
  const trimmed = value?.trim()
  if (!trimmed) return null
  if (['dev', 'latest', 'unknown'].includes(trimmed.toLowerCase())) return null
  return trimmed
}

export function buildLabel({ apiBuild, apiVersion, fallbackBuild }: BuildInfo): string {
  return meaningful(apiBuild) || meaningful(apiVersion) || meaningful(fallbackBuild) || 'dev'
}

export function visibleCommit(commit?: string | null): string | null {
  const value = meaningful(commit)
  return value ? value.slice(0, 7) : null
}
