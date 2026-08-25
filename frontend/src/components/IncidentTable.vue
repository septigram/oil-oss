<template>
  <q-table
    :rows="items"
    :columns="columns"
    row-key="incident_id"
    :loading="loading"
    v-model:pagination="pagination"
    dense
    flat
    bordered
    hide-pagination
    @row-click="(_evt, row) => emit('row-click', row)"
  >
    <template #header-cell-occurred_at="props">
      <q-th :props="props" class="cursor-pointer sortable-header" @click="toggleSort">
        発生日時
        <q-icon :name="sortIcon" size="xs" class="q-ml-xs" />
      </q-th>
    </template>
    <template #body-cell-occurred_at="props">
      <q-td :props="props">{{ formatDate(props.row.occurred_at) }}</q-td>
    </template>
    <template #body-cell-status_label="props">
      <q-td :props="props">
        <span
          :class="{
            'status-resolved': props.row.status === 'RESOLVED',
            'status-open': props.row.status === 'OPEN',
            'status-in-progress': props.row.status === 'IN_PROGRESS',
          }"
        >
          {{ props.row.status_label }}
        </span>
      </q-td>
    </template>
    <template #body-cell-severity="props">
      <q-td :props="props">
        <SeverityChip :severity="props.row.severity" />
      </q-td>
    </template>
    <template #body-cell-score="props">
      <q-td :props="props">
        {{ props.row.score != null ? props.row.score : '—' }}
      </q-td>
    </template>
    <template #bottom>
      <div class="row full-width justify-center q-pa-sm">
        <q-pagination
          :model-value="page"
          :max="Math.max(1, Math.ceil(total / pageSize))"
          @update:model-value="(p: number) => emit('page-change', p)"
        />
      </div>
    </template>
  </q-table>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { QTableColumn } from 'quasar'
import type { IncidentListItem } from '@/api/client'
import { createIncidentTablePagination } from '@/components/incidentTablePagination'
import SeverityChip from '@/components/SeverityChip.vue'

const props = defineProps<{
  items: IncidentListItem[]
  loading: boolean
  total: number
  page: number
  pageSize: number
  sort?: string
  showScore?: boolean
}>()

const emit = defineEmits<{
  'row-click': [row: IncidentListItem]
  'page-change': [page: number]
  'sort-change': [sort: string]
}>()

const effectiveSort = computed(() => props.sort || '-occurred_at')

const sortIcon = computed(() =>
  effectiveSort.value === 'occurred_at' ? 'arrow_upward' : 'arrow_downward',
)

function toggleSort() {
  const next = effectiveSort.value === '-occurred_at' ? 'occurred_at' : '-occurred_at'
  emit('sort-change', next)
}

/** rowsNumber を指定してサーバー側ページネーションとし、クライアント側の行数制限を無効化する */
const pagination = computed({
  get: () => createIncidentTablePagination(props.page, props.pageSize, props.total),
  set: (value) => {
    if (value.page !== props.page) {
      emit('page-change', value.page)
    }
  },
})

const columns = computed((): QTableColumn[] => {
  const base: QTableColumn[] = [
    { name: 'occurred_at', label: '発生日時', field: 'occurred_at', align: 'left' },
    { name: 'title', label: 'タイトル', field: 'title', align: 'left' },
    { name: 'status_label', label: '状態', field: 'status_label', align: 'left' },
    { name: 'severity', label: '重要度', field: 'severity', align: 'left' },
    { name: 'response_count', label: '対応件数', field: 'response_count', align: 'right' },
  ]
  if (props.showScore) {
    base.push({ name: 'score', label: '類似度', field: 'score', align: 'right' })
  }
  return base
})

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('ja-JP')
}
</script>

<style scoped>
.status-resolved {
  color: #99f;
}

.status-open {
  color: #00c;
  font-weight: 600;
}

.status-in-progress {
  color: #00c;
  font-weight: normal;
}

.sortable-header {
  user-select: none;
}
</style>
