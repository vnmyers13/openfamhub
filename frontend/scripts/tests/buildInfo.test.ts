import assert from 'node:assert/strict'
import test from 'node:test'

import { buildLabel } from '../../src/lib/buildInfo.ts'

test('buildLabel prefers the published API build over the frontend fallback', () => {
  assert.equal(
    buildLabel({ apiBuild: '0.51', apiVersion: '0.50', fallbackBuild: 'dev' }),
    '0.51',
  )
})

test('buildLabel falls back to API version when build is missing', () => {
  assert.equal(
    buildLabel({ apiVersion: '0.50', fallbackBuild: 'dev' }),
    '0.50',
  )
})

test('buildLabel falls back to frontend build when API health is unavailable', () => {
  assert.equal(buildLabel({ fallbackBuild: 'dev' }), 'dev')
})
