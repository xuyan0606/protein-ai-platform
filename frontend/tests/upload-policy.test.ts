import assert from 'node:assert/strict'
import test from 'node:test'
import { hasUploadSession, isAuthFailureStatus, uploadBatch } from '../src/lib/upload-policy.ts'

test('blocks upload when there is no login token', () => {
  assert.equal(hasUploadSession(null), false)
})

test('allows upload when a login token exists', () => {
  assert.equal(hasUploadSession('access-token'), true)
})

test('identifies expired or rejected upload sessions', () => {
  assert.equal(isAuthFailureStatus(401), true)
  assert.equal(isAuthFailureStatus(403), true)
  assert.equal(isAuthFailureStatus(500), false)
})

test('keeps successful uploads when another file fails', async () => {
  const files = [
    new File(['first'], 'first.pdb'),
    new File(['second'], 'second.pdb'),
  ]

  const result = await uploadBatch(files, async (file) => {
    if (file.name === 'second.pdb') throw new Error('network error')
    return { id: file.name }
  })

  assert.deepEqual(result, {
    uploaded: [{ id: 'first.pdb' }],
    failed: 1,
  })
})
