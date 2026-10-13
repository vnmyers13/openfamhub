import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Pin the zone so date tests behave the same on every machine and in CI.
// America/Detroit is west of UTC, where all-day off-by-one bugs show up.
process.env.TZ = 'America/Detroit'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
