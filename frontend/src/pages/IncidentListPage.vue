<template>
  <q-page padding>
    <IncidentSearchForm v-model="localParams" @search="search" />
    <div class="row q-mb-md q-gutter-sm justify-end">
      <q-btn color="primary" label="新規インシデント" :to="{ name: 'create' }" />
    </div>
    <IncidentTable
      :items="items"
      :loading="loading"
      :total="total"
      :page="localParams.page || 1"
      :page-size="localParams.page_size || INCIDENT_LIST_PAGE_SIZE"
      :sort="localParams.sort"
      :show-score="!!localParams.rag"
      @row-click="goDetail"
      @page-change="onPageChange"
      @sort-change="onSortChange"
    />
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Notify } from 'quasar'
import { fetchIncidents, type IncidentListItem, type SearchParams } from '@/api/client'
import { useIncidentStore, INCIDENT_LIST_PAGE_SIZE } from '@/stores/incidentStore'
import { formatApiError } from '@/utils/apiError'
import IncidentSearchForm from '@/components/IncidentSearchForm.vue'
import IncidentTable from '@/components/IncidentTable.vue'

const router = useRouter()
const route = useRoute()
const incidentStore = useIncidentStore()
const items = ref<IncidentListItem[]>([])
const total = ref(0)
const loading = ref(false)
const localParams = ref<SearchParams>({ ...incidentStore.searchParams })

function syncStore() {
  const next: SearchParams = { ...localParams.value }
  if (!next.initial) {
    delete next.initial
  }
  delete next.quick
  incidentStore.searchParams = next
  localParams.value = next
}

async function loadIncidents() {
  loading.value = true
  try {
    const data = await fetchIncidents(localParams.value)
    items.value = data.items
    total.value = data.total
  } catch (err) {
    Notify.create({
      type: 'negative',
      message: formatApiError(err, 'インシデント一覧の取得に失敗しました'),
    })
  } finally {
    loading.value = false
  }
}

function search() {
  localParams.value.page = 1
  delete localParams.value.initial
  syncStore()
  void loadIncidents()
}

function goDetail(row: IncidentListItem) {
  incidentStore.contextIncidentId = row.incident_id
  router.push({ name: 'detail', params: { id: row.incident_id } })
}

function onPageChange(page: number) {
  localParams.value.page = page
  syncStore()
  void loadIncidents()
}

function onSortChange(sort: string) {
  localParams.value.sort = sort
  localParams.value.page = 1
  syncStore()
  void loadIncidents()
}

watch(
  () => incidentStore.searchParams,
  (p) => {
    localParams.value = { ...p }
    void loadIncidents()
  },
  { deep: true },
)

onMounted(() => {
  if (route.name === 'list') void loadIncidents()
})
</script>
