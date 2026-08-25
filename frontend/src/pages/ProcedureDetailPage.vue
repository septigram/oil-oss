<template>
  <q-page padding v-if="detail">
    <div class="row q-mb-md items-center">
      <q-btn flat label="一覧に戻る" icon="arrow_back" :to="{ name: 'procedure-list' }" />
      <div class="row col q-gutter-sm justify-end">
        <q-btn color="primary" label="編集" :to="{ name: 'procedure-edit', params: { id: procedureId } }" />
        <q-toggle v-model="activeLocal" label="有効" @update:model-value="toggleActive" />
      </div>
    </div>

    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="text-h6">{{ detail.title }}</div>
        <div class="text-caption q-mt-xs">ID: {{ detail.procedure_id }}</div>
        <q-separator class="q-my-md" />
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-4"><strong>使用回数:</strong> {{ detail.usage_count }}</div>
          <div class="col-4">
            <strong>成功率:</strong>
            {{ detail.success_rate != null ? `${detail.success_rate}%` : '—' }}
          </div>
          <div class="col-4"><strong>種類:</strong> {{ detail.type_name || detail.type_id }}</div>
          <div class="col-4" v-if="detail.source_incident_id">
            <strong>元インシデント:</strong>
            <router-link :to="{ name: 'detail', params: { id: detail.source_incident_id } }">
              {{ detail.source_incident_id }}
            </router-link>
          </div>
        </div>
        <div class="q-mb-md">
          <div class="text-subtitle2">問題説明</div>
          <div class="markdown-body" v-html="renderMarkdown(detail.problem_description)" />
        </div>
        <div class="q-mb-md">
          <div class="text-subtitle2">対応手順</div>
          <div class="markdown-body" v-html="renderMarkdown(detail.procedure_steps)" />
        </div>
        <div v-if="detail.precautions" class="q-mb-md">
          <div class="text-subtitle2">注意事項</div>
          <div class="markdown-body" v-html="renderMarkdown(detail.precautions)" />
        </div>
        <div v-if="detail.required_tools">
          <div class="text-subtitle2">必要機材</div>
          <div class="markdown-body" v-html="renderMarkdown(detail.required_tools)" />
        </div>
      </q-card-section>
    </q-card>

    <q-card flat bordered>
      <q-card-section>
        <div class="text-subtitle1 q-mb-md">適用インシデント</div>
        <q-list bordered separator v-if="incidents.length">
          <q-item
            v-for="inc in incidents"
            :key="`${inc.incident_id}-${inc.applied_at}`"
            clickable
            :to="{ name: 'detail', params: { id: inc.incident_id } }"
          >
            <q-item-section>
              <q-item-label>{{ inc.title }}</q-item-label>
              <q-item-label caption>
                {{ inc.incident_id }} / {{ inc.status }}
                / 成功: {{ inc.was_successful == null ? '未入力' : inc.was_successful ? 'はい' : 'いいえ' }}
              </q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
        <div v-else class="text-grey">適用履歴はありません</div>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuasar } from 'quasar'
import {
  fetchProcedureDetail,
  fetchProcedureIncidents,
  updateProcedure,
} from '@/api/client'
import { useProcedureStore } from '@/stores/procedureStore'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const $q = useQuasar()
const procedureStore = useProcedureStore()
const procedureId = computed(() => String(route.params.id))
const detail = ref<Record<string, any> | null>(null)
const incidents = ref<Array<Record<string, any>>>([])
const activeLocal = ref(true)

async function load() {
  detail.value = await fetchProcedureDetail(procedureId.value)
  activeLocal.value = detail.value?.is_active ?? true
  incidents.value = await fetchProcedureIncidents(procedureId.value)
  procedureStore.contextProcedureId = procedureId.value
}

async function toggleActive(val: boolean) {
  if (!detail.value) return
  try {
    await updateProcedure(procedureId.value, {
      title: detail.value.title,
      problem_description: detail.value.problem_description,
      type_id: detail.value.type_id,
      importance: detail.value.importance,
      procedure_steps: detail.value.procedure_steps,
      required_tools: detail.value.required_tools,
      precautions: detail.value.precautions,
      estimated_time: detail.value.estimated_time,
      source_incident_id: detail.value.source_incident_id,
      tags: detail.value.tags,
      is_active: val,
    })
    $q.notify({ type: 'positive', message: val ? '手順書を有効化しました' : '手順書を無効化しました' })
    await load()
  } catch {
    activeLocal.value = !val
    $q.notify({ type: 'negative', message: '更新に失敗しました' })
  }
}

watch(procedureId, load)
watch(() => procedureStore.detailReloadNonce, load)
onMounted(load)
</script>

<style scoped>
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
