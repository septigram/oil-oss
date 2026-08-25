<template>
  <q-page padding>
    <div class="row q-mb-md">
      <q-btn flat label="保存せずに戻る" icon="arrow_back" :to="cancelTo" />
    </div>
    <IncidentEditForm
      :incident-id="incidentId"
      :is-new="isNew"
      @saved="onSaved"
    />
  </q-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import IncidentEditForm from '@/components/IncidentEditForm.vue'
import { useIncidentStore } from '@/stores/incidentStore'

const route = useRoute()
const router = useRouter()
const incidentStore = useIncidentStore()
const incidentId = computed(() => (route.params.id ? String(route.params.id) : null))
const isNew = computed(() => route.name === 'create')
const cancelTo = computed(() => (isNew.value ? { name: 'list' } : { name: 'detail', params: { id: incidentId.value } }))

function onSaved(id: string) {
  incidentStore.contextIncidentId = id
  if (isNew.value) router.push({ name: 'detail', params: { id }, query: { triage: '1' } })
  else router.push({ name: 'detail', params: { id } })
}
</script>
