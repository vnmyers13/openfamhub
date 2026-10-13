/** IANA timezones for the family timezone pickers (setup and settings). */

export function deviceZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

const COMMON = ['UTC', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles']

/** `first`, then common US zones, then every zone the browser knows. */
export function allZones(first: string): string[] {
  let zones: string[]
  try {
    zones = (Intl as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.('timeZone') ?? []
  } catch {
    zones = []
  }
  return Array.from(new Set([first, ...COMMON, ...zones]))
}

export function zoneLabel(zone: string): string {
  return zone.replace(/_/g, ' ')
}
