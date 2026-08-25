<template>
  <div class="nav-section q-pa-sm">
    <q-btn
      color="primary"
      no-caps
      unelevated
      class="full-width q-mb-xs"
      label="インシデント一覧"
      @click="emit('navigate', 'incidentList')"
    />
    <QuickFilterList @select="emit('quick', $event)" />

    <q-btn
      color="primary"
      no-caps
      unelevated
      class="full-width q-mt-md q-mb-xs"
      label="手順書一覧"
      @click="emit('navigate', 'procedureList')"
    />
    <q-list dense bordered separator v-if="topProcedures.length">
      <q-item
        v-for="p in topProcedures"
        :key="p.procedure_id"
        clickable
        :to="{ name: 'procedure-detail', params: { id: p.procedure_id } }"
        class="top-procedures-item"
      >
        <q-item-section>
          <q-item-label lines="2">{{ p.title }}</q-item-label>
          <q-item-label caption>{{ p.procedure_id }} / {{ p.usage_count }}回</q-item-label>
        </q-item-section>
      </q-item>
    </q-list>
    <div v-else class="text-grey text-caption q-px-sm">データなし</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchProcedures, type ProcedureListItem } from '@/api/client'
import QuickFilterList from '@/components/QuickFilterList.vue'

const emit = defineEmits<{
  quick: ['thisMonth' | 'lastMonth' | 'unresolved']
  navigate: ['incidentList' | 'procedureList']
}>()
const topProcedures = ref<ProcedureListItem[]>([])

async function loadTop() {
  const data = await fetchProcedures({
    page: 1,
    page_size: 5,
    sort: '-usage_count',
    is_active: true,
  })
  topProcedures.value = data.items
}

onMounted(() => {
  void loadTop()
})
</script>

<style lang="css" scoped>
.top-procedures-item {
  background: #fff;
}
</style>
