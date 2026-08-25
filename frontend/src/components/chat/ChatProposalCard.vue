<template>
  <q-card flat bordered class="chat-proposal q-mt-sm">
    <q-card-section class="q-py-sm">
      <div class="text-subtitle2">{{ fieldLabel }}</div>
      <div class="text-caption text-grey-7 q-mb-xs">{{ proposal.reason }}</div>
      <div class="row q-col-gutter-sm items-center">
        <div class="col">
          <span class="text-grey-7">現在:</span> {{ formatValue(proposal.current) }}
        </div>
        <div class="col-auto">→</div>
        <div class="col">
          <span class="text-primary">提案:</span> {{ formatValue(proposal.proposed) }}
        </div>
      </div>
      <div v-if="proposal.status === 'accepted'" class="text-caption text-positive q-mt-xs">
        受け入れ済み
      </div>
      <div v-else-if="proposal.status === 'rejected'" class="text-caption text-grey q-mt-xs">
        却下済み
      </div>
      <div v-else class="q-mt-sm row q-gutter-sm">
        <q-btn dense color="primary" label="受け入れる" :loading="loading" @click="accept" />
        <q-btn dense flat label="却下" :disable="loading" @click="reject" />
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuasar } from 'quasar'
import type { ChatProposal } from '@/stores/chatStore'
import { applyProposalToIncident } from '@/composables/useTriage'
import { useChatStore } from '@/stores/chatStore'
import { formatApiError } from '@/utils/apiError'

const FIELD_LABELS: Record<string, string> = {
  severity: '重要度',
  type_id: '種類',
  location_name: '発生個所',
  occurred_at: '発生日時',
  detected_at: '検知日時',
  affected_service_ids: '影響サービス',
  customer_ids: '影響顧客',
}

const props = defineProps<{
  proposal: ChatProposal
  incidentId: string | null
}>()

const emit = defineEmits<{ accepted: [] }>()

const chatStore = useChatStore()
const $q = useQuasar()
const loading = ref(false)

const fieldLabel = computed(
  () => FIELD_LABELS[props.proposal.field] ?? props.proposal.field,
)

function formatValue(value: unknown): string {
  if (value == null) return '—'
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}

async function accept() {
  if (!props.incidentId) return
  loading.value = true
  try {
    await applyProposalToIncident(props.incidentId, props.proposal)
    chatStore.updateProposalStatus(props.proposal.proposal_id, 'accepted')
    emit('accepted')
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '提案の反映に失敗しました') })
  } finally {
    loading.value = false
  }
}

function reject() {
  chatStore.updateProposalStatus(props.proposal.proposal_id, 'rejected')
}
</script>
