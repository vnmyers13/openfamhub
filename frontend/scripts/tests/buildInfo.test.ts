import assert from 'node:assert/strict'
import test from 'node:test'

import { buildLabel, visibleCommit } from '../../src/lib/buildInfo.ts'

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

test('buildLabel ignores placeholder API builds before falling back to API version', () => {
  assert.equal(
    buildLabel({ apiBuild: 'latest', apiVersion: '0.52', fallbackBuild: 'dev' }),
    '0.52',
  )
})

test('visibleCommit shortens real commit hashes', () => {
  assert.equal(visibleCommit('abcdef123'), 'abcdef1')
})

test('visibleCommit hides placeholder and missing commits', () => {
  assert.equal(visibleCommit('unknown'), null)
  assert.equal(visibleCommit(null), null)
})
