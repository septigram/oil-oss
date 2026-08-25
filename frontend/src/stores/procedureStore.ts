import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ProcedureSearchParams } from '@/api/client'

export const PROCEDURE_LIST_PAGE_SIZE = 20

export const useProcedureStore = defineStore('procedure', () => {
  const searchParams = ref<ProcedureSearchParams>({
    page: 1,
    page_size: PROCEDURE_LIST_PAGE_SIZE,
    is_active: true,
    sort: '-updated_at',
    rag: false,
  })
  const contextProcedureId = ref<string | null>(null)
  const detailReloadNonce = ref(0)

  function requestDetailReload() {
    detailReloadNonce.value++
  }

  return {
    searchParams,
    contextProcedureId,
    detailReloadNonce,
    requestDetailReload,
  }
})
