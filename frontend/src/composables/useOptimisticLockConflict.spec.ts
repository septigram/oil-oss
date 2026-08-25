/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from 'vitest'
import { AxiosError } from 'axios'
import { isOptimisticLockConflict } from '@/api/client'

vi.mock('quasar', () => ({
  useQuasar: () => ({
    dialog: () => ({
      onOk: (fn: () => void) => ({ onCancel: () => ({ onDismiss: () => ({}) }), then: fn }),
      onCancel: () => ({ onDismiss: () => ({}) }),
      onDismiss: () => ({}),
    }),
  }),
}))

import { conflictMessage, useOptimisticLockConflict } from '@/composables/useOptimisticLockConflict'

describe('isOptimisticLockConflict', () => {
  it('detects 409 conflict response', () => {
    const err = new AxiosError('conflict')
    err.response = {
      status: 409,
      data: {
        detail: 'conflict',
        message: '他のユーザによって更新されました。',
        current: { row_version: 2 },
      },
      statusText: 'Conflict',
      headers: {},
      config: {} as never,
    }
    expect(isOptimisticLockConflict(err)).toBe(true)
  })

  it('rejects non-conflict errors', () => {
    const err = new AxiosError('bad request')
    err.response = {
      status: 400,
      data: { detail: 'validation error' },
      statusText: 'Bad Request',
      headers: {},
      config: {} as never,
    }
    expect(isOptimisticLockConflict(err)).toBe(false)
  })
})

describe('conflictMessage', () => {
  it('returns server message when present', () => {
    const err = new AxiosError('conflict')
    err.response = {
      status: 409,
      data: {
        detail: 'conflict',
        message: '競合メッセージ',
        current: {},
      },
      statusText: 'Conflict',
      headers: {},
      config: {} as never,
    }
    expect(conflictMessage(err)).toBe('競合メッセージ')
  })

  it('returns default message for unknown errors', () => {
    expect(conflictMessage(new Error('x'))).toContain('他のユーザによって更新されました')
  })
})

describe('useOptimisticLockConflict', () => {
  it('returns dialog helpers', () => {
    const { showConflictDialog, handleConflict, isOptimisticLockConflict: isConflict } =
      useOptimisticLockConflict()
    expect(typeof showConflictDialog).toBe('function')
    expect(typeof handleConflict).toBe('function')
    expect(typeof isConflict).toBe('function')
  })
})
