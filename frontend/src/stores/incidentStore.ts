import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SearchParams } from '@/api/client'

export const INCIDENT_LIST_PAGE_SIZE = 20

export const useIncidentStore = defineStore('incident', () => {
  const searchParams = ref<SearchParams>({
    initial: true,
    page: 1,
    page_size: INCIDENT_LIST_PAGE_SIZE,
    rag: false,
  })
  const contextIncidentId = ref<string | null>(null)
  const detailReloadNonce = ref(0)

  function requestDetailReload() {
    detailReloadNonce.value++
  }

  function setQuickFilter(filter: 'thisMonth' | 'lastMonth' | 'unresolved') {
    searchParams.value = { page: 1, page_size: INCIDENT_LIST_PAGE_SIZE, rag: false }
    if (filter === 'thisMonth') {
      // サーバ側基準日で今月範囲は API に任せず日付を空にしてクライアントから送る
      // クイックフィルタ用に occurred_from/to を基準日から算出するのは UI config 取得後
      searchParams.value.quick = 'thisMonth'
    } else if (filter === 'lastMonth') {
      searchParams.value.quick = 'lastMonth'
    } else {
      searchParams.value.status = ['OPEN', 'IN_PROGRESS']
      searchParams.value.quick = 'unresolved'
    }
  }

  function applyDateRange(from: string, to: string) {
    searchParams.value.occurred_from = from
    searchParams.value.occurred_to = to
    delete searchParams.value.initial
    delete searchParams.value.quick
  }

  return { searchParams, contextIncidentId, detailReloadNonce, setQuickFilter, applyDateRange, requestDetailReload }
})
