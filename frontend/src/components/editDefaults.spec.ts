/**
 * @vitest-environment jsdom
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { getSettings, nowLocalDateTime } from '@/components/editDefaults'
import { useAuthStore } from '@/stores/authStore'

describe('nowLocalDateTime', () => {
  it('returns datetime-local format', () => {
    expect(nowLocalDateTime()).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
  })
})

describe('getSettings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('uses authStore employee and department', () => {
    const auth = useAuthStore()
    auth.$patch({
      user: {
        user_id: 'USR-00001',
        employee_id: 'EMP-00099',
        display_name: 'テスト',
        roles: ['OPERATOR'],
      },
      departmentId: 'DEPT-TEST',
    })

    const settings = getSettings()
    expect(settings.operatorId).toBe('EMP-00099')
    expect(settings.departmentId).toBe('DEPT-TEST')
  })
})
