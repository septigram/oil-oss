<template>
  <q-page padding>
    <div class="row q-mb-md">
      <q-btn flat label="保存せずに戻る" icon="arrow_back" :to="cancelTo" />
    </div>
    <q-banner v-if="draftError" class="bg-negative text-white q-mb-md" rounded>
      {{ draftError }}
      <template #action>
        <q-btn
          v-if="fromIncidentId"
          flat
          color="white"
          label="インシデント詳細へ"
          :to="{ name: 'detail', params: { id: fromIncidentId } }"
        />
      </template>
    </q-banner>
    <div class="relative-position">
      <q-inner-loading :showing="draftLoading" label="手順書下書きを生成しています..." />
      <ProcedureEditForm
        v-if="!draftError"
        :procedure-id="procedureId"
        :is-new="isNew"
        :initial-data="initialData"
        @saved="onSaved"
      />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import ProcedureEditForm from '@/components/ProcedureEditForm.vue'
import { buildProcedureFromIncident } from '@/api/client'
import { useProcedureStore } from '@/stores/procedureStore'
import { formatApiError } from '@/utils/apiError'

const route = useRoute()
const router = useRouter()
const $q = useQuasar()
const procedureStore = useProcedureStore()
const procedureId = computed(() => (route.params.id ? String(route.params.id) : null))
const isNew = computed(() => route.name === 'procedure-create')
const initialData = ref<Record<string, unknown> | null>(null)
const draftLoading = ref(false)
const draftError = ref<string | null>(null)
const fromIncidentId = computed(() =>
  route.query.from_incident ? String(route.query.from_incident) : null,
)

const cancelTo = computed(() =>
  isNew.value
    ? { name: 'procedure-list' }
    : { name: 'procedure-detail', params: { id: procedureId.value } },
)

function onSaved(id: string) {
  procedureStore.contextProcedureId = id
  router.push({ name: 'procedure-detail', params: { id } })
}

onMounted(async () => {
  const incidentId = fromIncidentId.value
  if (!isNew.value || !incidentId) return
  draftLoading.value = true
  draftError.value = null
  try {
    const result = await buildProcedureFromIncident(incidentId)
    initialData.value = result.preview
    if (result.meta.source === 'rule_based') {
      $q.notify({
        type: 'info',
        message: 'AI 生成に失敗したため、たたき台を表示しています',
        caption: result.meta.fallback_reason,
        timeout: 8000,
      })
    }
  } catch (err: unknown) {
    draftError.value = formatApiError(err, '手順書下書きの生成に失敗しました')
    $q.notify({ type: 'negative', message: draftError.value })
  } finally {
    draftLoading.value = false
  }
})
</script>
