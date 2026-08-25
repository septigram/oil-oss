/**
 * @vitest-environment jsdom
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useUiStore } from '@/stores/uiStore'

describe('uiStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with server reachable', () => {
    const store = useUiStore()
    expect(store.serverReachable).toBe(true)
  })

  it('updates server reachability', () => {
    const store = useUiStore()
    store.setServerReachable(false)
    expect(store.serverReachable).toBe(false)
    store.setServerReachable(true)
    expect(store.serverReachable).toBe(true)
  })

  it('starts with log panel hidden', () => {
    const store = useUiStore()
    expect(store.showLogPanel).toBe(false)
    store.showLogPanel = true
    expect(store.showLogPanel).toBe(true)
    store.showLogPanel = false
    expect(store.showLogPanel).toBe(false)
  })
})
