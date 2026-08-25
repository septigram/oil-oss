<template>
  <q-card flat bordered>
    <q-card-section>
      <div class="text-subtitle2">{{ editing ? '対応編集' : '対応新規登録' }}</div>
      <q-form ref="formRef" class="q-gutter-md q-mt-sm" @submit.prevent="save">
        <q-select
          v-model="form.response_type"
          :options="typeOptions"
          label="対応種別"
          outlined
          dense
          emit-value
          map-options
        />
        <q-input v-model="form.summary" label="概要 *" outlined dense :rules="[requiredRule]" />
        <q-input v-model="form.detail" label="詳細 *" type="textarea" outlined dense :rules="[requiredRule]" />
        <q-input
          v-model="form.started_at"
          label="開始日時 *"
          outlined
          dense
          type="datetime-local"
          :rules="[requiredRule]"
        />
        <q-input v-model="form.ended_at" label="終了日時" outlined dense type="datetime-local" clearable />
        <div class="row q-gutter-sm justify-end">
          <q-btn type="submit" color="primary" :label="editing ? '更新' : '登録'" :loading="saving" />
          <q-btn v-if="editing" flat label="キャンセル" @click="emit('cancel')" />
        </div>
      </q-form>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useQuasar, type QForm } from 'quasar'
import { createResponse, fetchIncidentDetail, updateResponse } from '@/api/client'
import { useOptimisticLockConflict } from '@/composables/useOptimisticLockConflict'
import { formatApiError } from '@/utils/apiError'

const props = defineProps<{
  incidentId: string
  editing: Record<string, any> | null
}>()

const emit = defineEmits<{ saved: []; cancel: [] }>()

const $q = useQuasar()
const { handleConflict } = useOptimisticLockConflict()

const formRef = ref<QForm | null>(null)
const saving = ref(false)
const rowVersion = ref(1)
const requiredRule = (val: string | null | undefined) => !!val?.trim() || '必須項目です'
const typeOptions = [
  { label: '初期対応', value: 'INITIAL' },
  { label: '二次対応', value: 'SECONDARY' },
  { label: '三次対応', value: 'TERTIARY' },
  { label: '恒久対応', value: 'PERMANENT' },
]

const form = reactive({
  response_type: 'SECONDARY',
  summary: '',
  detail: '',
  started_at: '',
  ended_at: '',
})

watch(
  () => props.editing,
  (r) => {
    if (r) {
      form.response_type = r.response_type
      form.summary = r.summary
      form.detail = r.detail
      form.started_at = toLocalInput(r.started_at)
      form.ended_at = r.ended_at ? toLocalInput(r.ended_at) : ''
      rowVersion.value = Number(r.row_version ?? 1)
    } else {
      form.response_type = 'SECONDARY'
      form.summary = ''
      form.detail = ''
      form.started_at = nowLocalInput()
      form.ended_at = ''
      rowVersion.value = 1
    }
  },
  { immediate: true },
)

async function reloadFromServer() {
  if (!props.editing) return
  const detail = await fetchIncidentDetail(props.incidentId)
  const fresh = detail.responses?.find(
    (r: { response_id: string }) => r.response_id === props.editing?.response_id,
  )
  if (!fresh) return
  form.response_type = fresh.response_type
  form.summary = fresh.summary
  form.detail = fresh.detail
  form.started_at = toLocalInput(fresh.started_at)
  form.ended_at = fresh.ended_at ? toLocalInput(fresh.ended_at) : ''
  rowVersion.value = Number(fresh.row_version ?? 1)
}

function toLocalInput(iso: string) {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function nowLocalInput() {
  return toLocalInput(new Date().toISOString())
}

function toIso(local: string) {
  return local ? new Date(local).toISOString() : null
}

async function save() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  saving.value = true
  try {
    const body = {
      response_type: form.response_type,
      summary: form.summary,
      detail: form.detail,
      started_at: toIso(form.started_at),
      ended_at: form.ended_at ? toIso(form.ended_at) : null,
    }
    if (props.editing) {
      await updateResponse(props.incidentId, props.editing.response_id, {
        ...body,
        row_version: rowVersion.value,
      })
    } else {
      await createResponse(props.incidentId, body)
    }
    emit('saved')
  } catch (err: unknown) {
    const handled = await handleConflict(err, reloadFromServer)
    if (!handled) {
      $q.notify({ type: 'negative', message: formatApiError(err, '登録に失敗しました') })
    }
  } finally {
    saving.value = false
  }
}
</script>
