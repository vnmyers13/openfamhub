export interface CyclePanel { id: string; label: string; durationSeconds: number }

export interface CycleState {
  panel: CyclePanel | null
  index: number
  secondsLeft: number
  elapsedInPanel: number
}

export const WALL_CYCLE_PANELS: CyclePanel[] = [
]

const duration = (panel: CyclePanel) => Math.max(1, panel.durationSeconds)

export function cycleState(panels: CyclePanel[], nowMs: number, startedAtMs: number): CycleState {
  if (panels.length === 0) return { panel: null, index: -1, secondsLeft: 0, elapsedInPanel: 0 }
  const total = panels.reduce((sum, panel) => sum + duration(panel), 0)
  let elapsed = Math.max(0, Math.floor((nowMs - startedAtMs) / 1000)) % total
  for (let index = 0; index < panels.length; index += 1) {
    const panelDuration = duration(panels[index])
    if (elapsed < panelDuration) {
      return { panel: panels[index], index, elapsedInPanel: elapsed, secondsLeft: panelDuration - elapsed }
    }
    elapsed -= panelDuration
  }
  return { panel: panels[0], index: 0, secondsLeft: duration(panels[0]), elapsedInPanel: 0 }
}
