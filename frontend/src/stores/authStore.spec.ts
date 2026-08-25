/**
 * @vitest-environment jsdom
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/authStore'

vi.mock('@/api/client', () => ({
  authFetchMe: vi.fn(),
  authLogin: vi.fn(),
  authLogout: vi.fn(),
  fetchMasters: vi.fn(),
  isAxios401: (err: unknown) =>
    !!err && typeof err === 'object' && 'response' in err && (err as { response?: { status?: number } }).response?.status === 401,
  registerUnauthorizedHandler: vi.fn(),
}))

import { authFetchMe, authLogin, authLogout, fetchMasters } from '@/api/client'

describe('authStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('identifies admin role', async () => {
    vi.mocked(authFetchMe).mockResolvedValue({
      user_id: 'USR-00001',
      employee_id: 'EMP-00001',
      display_name: '運用 一郎',
      roles: ['ADMIN', 'OPERATOR'],
    })
    vi.mocked(fetchMasters).mockResolvedValue([
      { employee_id: 'EMP-00001', employee_name: '運用 一郎', department_id: 'DEPT-OPS' },
    ])

    const store = useAuthStore()
    await store.fetchMe()

    expect(store.isAdmin).toBe(true)
    expect(store.isOperator).toBe(true)
    expect(store.displayName).toBe('運用 一郎')
    expect(store.departmentId).toBe('DEPT-OPS')
    expect(store.authEnabled).toBe(true)
  })

  it('treats dummy user as auth disabled', async () => {
    vi.mocked(authFetchMe).mockResolvedValue({
      user_id: 'USR-DUMMY',
      employee_id: 'EMP-00001',
      display_name: '運用 一郎',
      roles: ['ADMIN'],
    })
    vi.mocked(fetchMasters).mockResolvedValue([])

    const store = useAuthStore()
    await store.fetchMe()

    expect(store.authEnabled).toBe(false)
    expect(store.isAuthenticated).toBe(true)
  })

  it('clears session on 401', async () => {
    vi.mocked(authFetchMe).mockRejectedValue({ response: { status: 401 } })

    const store = useAuthStore()
    await expect(store.fetchMe()).rejects.toEqual({ response: { status: 401 } })

    expect(store.isAuthenticated).toBe(false)
    expect(store.authEnabled).toBe(true)
  })

  it('login sets user and auth enabled', async () => {
    vi.mocked(authLogin).mockResolvedValue({
      user_id: 'USR-00002',
      employee_id: 'EMP-00002',
      display_name: 'テスト 太郎',
      roles: ['OPERATOR'],
    })
    vi.mocked(fetchMasters).mockResolvedValue([
      { employee_id: 'EMP-00002', employee_name: 'テスト 太郎', department_id: 'DEPT-OPS' },
    ])

    const store = useAuthStore()
    await store.login('operator', 'secret')

    expect(store.employeeId).toBe('EMP-00002')
    expect(store.isOperator).toBe(true)
    expect(store.isAdmin).toBe(false)
  })

  it('logout clears session when auth enabled', async () => {
    vi.mocked(authFetchMe).mockResolvedValue({
      user_id: 'USR-00001',
      employee_id: 'EMP-00001',
      display_name: '運用 一郎',
      roles: ['ADMIN'],
    })
    vi.mocked(fetchMasters).mockResolvedValue([])
    vi.mocked(authLogout).mockResolvedValue(undefined)

    const store = useAuthStore()
    await store.fetchMe()
    await store.logout()

    expect(authLogout).toHaveBeenCalled()
    expect(store.isAuthenticated).toBe(false)
  })
})
