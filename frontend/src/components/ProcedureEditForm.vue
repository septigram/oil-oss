<template>
  <q-form class="q-gutter-md" @submit.prevent="save">
    <q-input v-model="form.title" label="タイトル *" maxlength="100" />
    <q-select
      v-model="form.type_id"
      :options="typeOptions"
      option-value="type_id"
      option-label="type_name"
      emit-value
      map-options
      label="種類 *"
    />
    <q-select
      v-model="form.importance"
      :options="importanceOptions"
      emit-value
      map-options
      label="重要度"
      clearable
    />
    <div>
      <div class="text-subtitle2">問題説明 *</div>
      <q-input v-model="form.problem_description" type="textarea" autogrow />
      <div class="q-mt-sm markdown-preview markdown-body" v-html="renderMarkdown(form.problem_description)" />
    </div>
    <div>
      <div class="text-subtitle2">対応手順 *</div>
      <q-input v-model="form.procedure_steps" type="textarea" autogrow />
      <div class="q-mt-sm markdown-preview markdown-body" v-html="renderMarkdown(form.procedure_steps)" />
    </div>
    <div>
      <div class="text-subtitle2">注意事項</div>
      <q-input v-model="form.precautions" type="textarea" autogrow />
    </div>
    <div>
      <div class="text-subtitle2">必要機材</div>
      <q-input v-model="form.required_tools" type="textarea" autogrow />
    </div>
    <q-input v-model="form.estimated_time" label="目安時間" />
    <q-input v-model="form.source_incident_id" label="元インシデント ID" />
    <q-input v-model="form.tags" label="タグ（カンマ区切り）" />
    <q-toggle v-model="form.is_active" label="有効" />
    <div class="row q-gutter-sm">
      <q-btn type="submit" color="primary" label="保存" :loading="saving" />
    </div>
  </q-form>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useQuasar } from 'quasar'
import { fetchMasters, fetchProcedureDetail, createProcedure, updateProcedure } from '@/api/client'
import { useOptimisticLockConflict } from '@/composables/useOptimisticLockConflict'
import { formatApiError } from '@/utils/apiError'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{
  procedureId: string | null
  isNew: boolean
  initialData?: Record<string, unknown> | null
}>()

const emit = defineEmits<{ saved: [id: string] }>()
const $q = useQuasar()
const { handleConflict } = useOptimisticLockConflict()
const saving = ref(false)
const rowVersion = ref(1)
const typeOptions = ref<Array<Record<string, string>>>([])

const importanceOptions = [
  { label: 'LOW', value: 'LOW' },
  { label: 'MEDIUM', value: 'MEDIUM' },
  { label: 'HIGH', value: 'HIGH' },
]

const form = ref({
  title: '',
  problem_description: '',
  type_id: '',
  importance: null as string | null,
  procedure_steps: '',
  required_tools: '',
  precautions: '',
  estimated_time: '',
  source_incident_id: '',
  tags: '',
  is_active: true,
})

function applyInitial(data: Record<string, unknown>) {
  form.value = {
    title: String(data.title || ''),
    problem_description: String(data.problem_description || ''),
    type_id: String(data.type_id || ''),
    importance: data.importance ? String(data.importance) : null,
    procedure_steps: String(data.procedure_steps || ''),
    required_tools: data.required_tools ? String(data.required_tools) : '',
    precautions: data.precautions ? String(data.precautions) : '',
    estimated_time: data.estimated_time ? String(data.estimated_time) : '',
    source_incident_id: data.source_incident_id ? String(data.source_incident_id) : '',
    tags: data.tags ? String(data.tags) : '',
    is_active: data.is_active !== false,
  }
}

async function load() {
  if (props.isNew) {
    if (props.initialData) applyInitial(props.initialData)
    rowVersion.value = 1
    return
  }
  if (!props.procedureId) return
  const data = await fetchProcedureDetail(props.procedureId)
  applyInitial(data)
  rowVersion.value = Number(data.row_version ?? 1)
}

async function save() {
  saving.value = true
  try {
    const body = { ...form.value, row_version: rowVersion.value }
    if (props.isNew) {
      const { row_version: _rv, ...createBody } = body
      const res = await createProcedure(createBody)
      emit('saved', res.procedure_id)
    } else if (props.procedureId) {
      await updateProcedure(props.procedureId, body)
      emit('saved', props.procedureId)
    }
  } catch (err: unknown) {
    const handled = await handleConflict(err, load)
    if (!handled) {
      $q.notify({ type: 'negative', message: formatApiError(err, '保存に失敗しました') })
    }
  } finally {
    saving.value = false
  }
}

watch(() => props.procedureId, load)
watch(() => props.initialData, (d) => { if (d && props.isNew) applyInitial(d) }, { deep: true })

onMounted(async () => {
  typeOptions.value = await fetchMasters('incident-types')
  await load()
})
</script>

<style scoped>
.markdown-preview {
  border: 1px solid #ddd;
  padding: 8px;
  border-radius: 4px;
  background: #fafafa;
}

.markdown-body :deep(p) {
  margin: 0 0 0.5em;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(:is(h1, h2, h3, h4, h5, h6)) {
  margin: 0.35em 0 0.2em;
  font-weight: 600;
  line-height: 1.4;
}

.markdown-body :deep(:is(h1, h2, h3, h4, h5, h6):first-child) {
  margin-top: 0;
}

.markdown-body :deep(h1) {
  font-size: 1.15em;
}

.markdown-body :deep(h2) {
  font-size: 1.1em;
}

.markdown-body :deep(h3) {
  font-size: 1.05em;
}

.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  font-size: 1em;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.25em 0 0.5em;
  padding-left: 1.25em;
}

.markdown-body :deep(li) {
  margin: 0.15em 0;
}

.markdown-body :deep(code) {
  font-family: Consolas, monospace;
  font-size: 0.9em;
  background: rgba(0, 0, 0, 0.06);
  padding: 0.1em 0.35em;
  border-radius: 3px;
}

.markdown-body :deep(pre) {
  margin: 0.5em 0;
  padding: 0.5em 0.75em;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.markdown-body :deep(strong) {
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: #1976d2;
  text-decoration: underline;
  cursor: pointer;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: 0.5em 0;
  border-collapse: collapse;
  font-size: 0.9em;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid rgba(0, 0, 0, 0.12);
  padding: 0.35em 0.6em;
  text-align: left;
  vertical-align: top;
}

.markdown-body :deep(th) {
  background: rgba(0, 0, 0, 0.04);
  font-weight: 600;
}
</style>
