export type BuildInfo = {
  apiBuild?: string | null
  apiVersion?: string | null
  fallbackBuild: string
}

export function buildLabel({ apiBuild, apiVersion, fallbackBuild }: BuildInfo): string {
  return apiBuild || apiVersion || fallbackBuild
}
