<template>
  <q-page padding>
    <ProcedureSearchForm v-model="localParams" @search="search" />
    <div class="row q-mb-md q-gutter-sm justify-end">
      <q-btn color="primary" label="新規手順書" :to="{ name: 'procedure-create' }" />
    </div>
    <q-table
      ref="tableRef"
      flat
      bordered
      :rows="items"
      :columns="columns"
      row-key="procedure_id"
      :loading="loading"
      v-model:pagination="tablePagination"
      @request="onRequest"
      @row-click="(_e, row) => goDetail(row)"
    >
      <template #header-cell-usage_count="props">
        <q-th :props="props" class="cursor-pointer sortable-header" @click="toggleUsageCountSort">
          使用回数
          <q-icon :name="usageCountSortIcon" size="xs" class="q-ml-xs" />
        </q-th>
      </template>
      <template #body-cell-success_rate="props">
        <q-td :props="props">
          {{ props.row.success_rate != null ? `${props.row.success_rate}%` : '—' }}
        </q-td>
      </template>
      <template #body-cell-is_active="props">
        <q-td :props="props">
          <q-badge :color="props.row.is_active ? 'positive' : 'grey'">
            {{ props.row.is_active ? '有効' : '無効' }}
          </q-badge>
        </q-td>
      </template>
      <template #body-cell-score="props">
        <q-td :props="props">
          {{ props.row.score != null ? props.row.score : '—' }}
        </q-td>
      </template>
    </q-table>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Notify } from 'quasar'
import type { QTable, QTableColumn } from 'quasar'
import {
  fetchProcedures,
  type ProcedureListItem,
  type ProcedureSearchParams,
} from '@/api/client'
import { useProcedureStore, PROCEDURE_LIST_PAGE_SIZE } from '@/stores/procedureStore'
import { formatApiError } from '@/utils/apiError'
import ProcedureSearchForm from '@/components/ProcedureSearchForm.vue'

const router = useRouter()
const procedureStore = useProcedureStore()
const tableRef = ref<QTable | null>(null)
const items = ref<ProcedureListItem[]>([])
const total = ref(0)
const loading = ref(false)
const localParams = ref<ProcedureSearchParams>({ ...procedureStore.searchParams })

const usageCountSortIcon = computed(() =>
  localParams.value.sort === 'usage_count' ? 'arrow_upward' : 'arrow_downward',
)

const columns = computed((): QTableColumn[] => {
  const base: QTableColumn[] = [
    { name: 'procedure_id', label: 'ID', field: 'procedure_id', align: 'left' },
    { name: 'title', label: 'タイトル', field: 'title', align: 'left' },
    { name: 'usage_count', label: '使用回数', field: 'usage_count', align: 'right' },
    { name: 'success_rate', label: '成功率', field: 'success_rate', align: 'right' },
    { name: 'is_active', label: '状態', field: 'is_active', align: 'center' },
    {
      name: 'updated_at',
      label: '更新日時',
      field: 'updated_at',
      align: 'left',
      format: (v: string) => new Date(v).toLocaleString('ja-JP'),
    },
  ]
  if (localParams.value.rag) {
    base.splice(2, 0, { name: 'score', label: '類似度', field: 'score', align: 'right' })
  }
  return base
})

const tablePagination = ref({
  page: 1,
  rowsPerPage: PROCEDURE_LIST_PAGE_SIZE,
  rowsNumber: 0,
  sortBy: 'updated_at',
  descending: true,
})

function syncStore() {
  procedureStore.searchParams = { ...localParams.value }
}

async function loadProcedures() {
  loading.value = true
  try {
    const data = await fetchProcedures(localParams.value)
    items.value = data.items
    total.value = data.total
    tablePagination.value.rowsNumber = data.total
    tablePagination.value.page = data.page
  } catch (err) {
    Notify.create({
      type: 'negative',
      message: formatApiError(err, '手順書一覧の取得に失敗しました'),
    })
  } finally {
    loading.value = false
  }
}

function search() {
  localParams.value.page = 1
  tablePagination.value.page = 1
  syncStore()
  void loadProcedures()
}

function toggleUsageCountSort() {
  const next = localParams.value.sort === '-usage_count' ? 'usage_count' : '-usage_count'
  localParams.value.sort = next
  localParams.value.page = 1
  tablePagination.value.sortBy = 'usage_count'
  tablePagination.value.descending = next === '-usage_count'
  tablePagination.value.page = 1
  syncStore()
  void loadProcedures()
}

function goDetail(row: ProcedureListItem) {
  procedureStore.contextProcedureId = row.procedure_id
  router.push({ name: 'procedure-detail', params: { id: row.procedure_id } })
}

function onRequest(props: {
  pagination: {
    page: number
    rowsPerPage: number
    rowsNumber?: number
    sortBy: string
    descending: boolean
  }
}) {
  const { page, rowsPerPage, sortBy, descending } = props.pagination
  tablePagination.value.page = page
  tablePagination.value.rowsPerPage = rowsPerPage
  tablePagination.value.sortBy = sortBy
  tablePagination.value.descending = descending
  localParams.value.page = page
  localParams.value.page_size = rowsPerPage
  if (sortBy === 'usage_count') {
    localParams.value.sort = descending ? '-usage_count' : 'usage_count'
  } else {
    localParams.value.sort = descending ? '-updated_at' : 'updated_at'
  }
  syncStore()
  void loadProcedures()
}

watch(
  () => procedureStore.searchParams,
  (p) => {
    localParams.value = { ...p }
    void loadProcedures()
  },
  { deep: true },
)

onMounted(() => {
  tableRef.value?.requestServerInteraction()
})
</script>

<style scoped>
.sortable-header {
  user-select: none;
}
</style>
