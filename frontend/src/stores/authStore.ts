import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  authFetchMe,
  authLogin,
  authLogout,
  fetchMasters,
  isAxios401,
  registerUnauthorizedHandler,
  type UserSummary,
} from '@/api/client'

export type Role = 'ADMIN' | 'OPERATOR' | 'VIEWER'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserSummary | null>(null)
  const departmentId = ref<string | null>(null)
  /** null = 未判定, true = セッション認証あり, false = auth.enabled 無効（ダミーユーザ） */
  const authEnabled = ref<boolean | null>(null)
  const initialized = ref(false)
  const loading = ref(false)

  const displayName = computed(() => user.value?.display_name ?? '')
  const employeeId = computed(() => user.value?.employee_id ?? '')
  const roles = computed(() => user.value?.roles ?? [])
  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => roles.value.includes('ADMIN'))
  const isOperator = computed(() => roles.value.includes('OPERATOR'))
  const isViewer = computed(() => roles.value.includes('VIEWER'))

  async function resolveDepartment(empId: string) {
    try {
      const employees = await fetchMasters('employees')
      const emp = employees.find((e) => e.employee_id === empId)
      departmentId.value = emp?.department_id ?? null
    } catch {
      departmentId.value = null
    }
  }

  function applyUser(me: UserSummary) {
    user.value = me
    if (me.user_id === 'USR-DUMMY') {
      authEnabled.value = false
    } else if (authEnabled.value !== true) {
      authEnabled.value = true
    }
  }

  function clearSession() {
    user.value = null
    departmentId.value = null
  }

  async function fetchMe() {
    try {
      const me = await authFetchMe()
      applyUser(me)
      await resolveDepartment(me.employee_id)
      return me
    } catch (err: unknown) {
      if (isAxios401(err)) {
        authEnabled.value = true
        clearSession()
      }
      throw err
    }
  }

  async function login(loginName: string, password: string) {
    loading.value = true
    try {
      const me = await authLogin({ login_name: loginName, password })
      applyUser(me)
      authEnabled.value = true
      await resolveDepartment(me.employee_id)
      return me
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    loading.value = true
    try {
      await authLogout()
      if (authEnabled.value) {
        clearSession()
      } else {
        await fetchMe().catch(() => {
          clearSession()
        })
      }
    } finally {
      loading.value = false
    }
  }

  async function initialize(onUnauthorized?: () => void) {
    if (initialized.value) return
    registerUnauthorizedHandler((url) => {
      if (!authEnabled.value) return
      if (url.includes('/auth/me') || url.includes('/auth/login')) return
      clearSession()
      onUnauthorized?.()
    })
    try {
      await fetchMe()
    } catch {
      // 未ログイン時の 401 は想定内
    }
    initialized.value = true
  }

  return {
    user,
    departmentId,
    authEnabled,
    initialized,
    loading,
    displayName,
    employeeId,
    roles,
    isAuthenticated,
    isAdmin,
    isOperator,
    isViewer,
    fetchMe,
    login,
    logout,
    initialize,
    clearSession,
  }
})
