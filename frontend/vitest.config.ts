import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Pin the zone so date tests behave the same on every machine and in CI.
// America/Detroit is west of UTC, where all-day off-by-one bugs show up.
process.env.TZ = 'America/Detroit'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // fake-indexeddb replaces a process-wide IndexedDB factory in offline tests.
    // Run files serially so one file cannot replace it during another's replay.
    fileParallelism: false,
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/**/fixtures.ts', 'src/test/**', 'src/main.tsx', 'src/vite-env.d.ts'],
      reporter: ['text', 'html'],
      // CI fails below these. Raise them as coverage grows; don't lower them to pass.
      thresholds: { statements: 85, branches: 75, functions: 80, lines: 85 },
    },
  },
})
