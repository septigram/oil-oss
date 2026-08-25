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
        <div class="col-12 col-md-3">
          <q-select
            v-model="model.type_id"
            dense
            outlined
            :options="typeOptions"
            option-value="type_id"
            option-label="type_name"
            emit-value
            map-options
            label="種類"
            clearable
          />
        </div>
        <div class="col-12 col-md-3">
          <q-select
            v-model="model.is_active"
            dense
            outlined
            :options="activeOptions"
            emit-value
            map-options
            label="有効/無効"
          />
        </div>
        <div class="col-12 col-md-3">
          <q-input v-model="model.tags" dense outlined label="タグ" clearable />
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
import { fetchMasters, type ProcedureSearchParams } from '@/api/client'

const model = defineModel<ProcedureSearchParams>({ required: true })
const emit = defineEmits<{ search: [] }>()

const showAdvanced = ref(false)

const typeOptions = ref<Array<Record<string, string>>>([])

const activeOptions = [
  { label: '有効のみ', value: true },
  { label: '無効のみ', value: false },
  { label: 'すべて', value: undefined },
]

onMounted(async () => {
  typeOptions.value = await fetchMasters('incident-types')
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
