import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useIncidentStore } from '@/stores/incidentStore'

describe('incidentStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('applies quick filter for unresolved incidents', () => {
    const store = useIncidentStore()
    store.setQuickFilter('unresolved')
    expect(store.searchParams.status).toEqual(['OPEN', 'IN_PROGRESS'])
    expect(store.searchParams.quick).toBe('unresolved')
    expect(store.searchParams.page).toBe(1)
  })

  it('sets quick marker for this month filter', () => {
    const store = useIncidentStore()
    store.setQuickFilter('thisMonth')
    expect(store.searchParams.quick).toBe('thisMonth')
    expect(store.searchParams.page).toBe(1)
  })

  it('applies explicit date range and clears initial flag', () => {
    const store = useIncidentStore()
    store.searchParams.initial = true
    store.applyDateRange('2020-05-01', '2020-05-31')
    expect(store.searchParams.occurred_from).toBe('2020-05-01')
    expect(store.searchParams.occurred_to).toBe('2020-05-31')
    expect(store.searchParams.initial).toBeUndefined()
  })
})
