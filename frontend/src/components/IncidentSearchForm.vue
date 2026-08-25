<template>
  <q-card flat bordered class="q-mb-md">
    <q-card-section>
      <div class="row q-col-gutter-sm items-center no-wrap search-basic-row">
        <div class="col search-keyword">
          <q-input
            v-model="model.keyword"
            dense
            outlined
            label="キーワード"
            clearable
            @keyup.enter="emit('search')"
          />
        </div>
        <div class="col-auto">
          <q-btn
            label="検索"
            :disable="!!model.rag && !model.keyword?.trim()"
            @click="emit('search')"
          />
        </div>
        <div class="col-auto">
          <q-btn
            flat
            dense
            no-caps
            :label="showAdvanced ? '詳細検索を非表示' : '詳細検索を表示'"
            @click="showAdvanced = !showAdvanced"
          />
        </div>
      </div>

      <div v-show="showAdvanced" class="row q-col-gutter-md q-mt-md">
        <div class="col-6 col-md-3">
          <q-input v-model="model.occurred_from" dense outlined label="発生日（から）" type="date" clearable />
        </div>
        <div class="col-6 col-md-3">
          <q-input v-model="model.occurred_to" dense outlined label="発生日（まで）" type="date" clearable />
        </div>
        <div class="col-12 col-md-3">
          <q-select
            v-model="model.status"
            dense
            outlined
            multiple
            use-chips
            label="状態"
            :options="statusOptions"
            emit-value
            map-options
            clearable
          />
        </div>
        <div class="col-12 col-md-3">
          <q-select
            v-model="model.severity"
            dense
            outlined
            multiple
            use-chips
            label="重要度"
            :options="severityOptions"
            emit-value
            map-options
            clearable
          />
        </div>
        <div class="col-12 col-md-3">
          <q-select
            v-model="model.type_id"
            dense
            outlined
            label="種類"
            :options="typeOptions"
            emit-value
            map-options
            clearable
          />
        </div>
        <div class="col-12 col-md-3 flex items-center">
          <q-checkbox
            :model-value="model.rag ?? false"
            dense
            label="RAG検索"
            @update:model-value="model.rag = $event"
          />
        </div>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { SearchParams } from '@/api/client'
import { fetchMasters } from '@/api/client'

const model = defineModel<SearchParams>({ required: true })
const emit = defineEmits<{ search: [] }>()

const showAdvanced = ref(false)

const statusOptions = [
  { label: '未着手', value: 'OPEN' },
  { label: '対応中', value: 'IN_PROGRESS' },
  { label: '解決済み', value: 'RESOLVED' },
]
const severityOptions = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((v) => ({ label: v, value: v }))
const typeOptions = ref<Array<{ label: string; value: string }>>([])

onMounted(async () => {
  const types = await fetchMasters('incident-types')
  typeOptions.value = types.map((t) => ({ label: t.type_name, value: t.type_id }))
})
</script>

<style scoped>
.search-basic-row {
  flex-wrap: nowrap;
}

.search-keyword {
  min-width: 0;
}
</style>
