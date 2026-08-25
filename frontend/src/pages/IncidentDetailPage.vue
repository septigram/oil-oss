<template>
  <q-page padding v-if="detail">
    <div class="row q-mb-md items-center">
      <q-btn flat label="一覧に戻る" icon="arrow_back" :to="{ name: 'list' }" />
      <div class="row col q-gutter-sm justify-end">
        <q-btn color="primary" label="編集" :to="{ name: 'edit', params: { id: incidentId } }" />
        <q-btn
          color="secondary"
          label="類似インシデントを探す"
          icon="travel_explore"
          :disable="streaming"
          @click="findSimilarIncidents"
        />
      </div>
    </div>

    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="text-h6">{{ detail.incident.title }}</div>
        <div class="text-caption q-mt-xs">ID: {{ detail.incident.incident_id }}</div>
        <q-separator class="q-my-md" />
        <div class="row q-col-gutter-md">
          <div class="col-6"><strong>発生日時:</strong> {{ fmt(detail.incident.occurred_at) }}</div>
          <div class="col-6"><strong>検知日時:</strong> {{ fmt(detail.incident.detected_at) }}</div>
          <div class="col-6"><strong>状態:</strong> {{ incidentStatusLabel }}</div>
          <div class="col-6 severity-field">
            <strong>重要度:</strong>
            <SeverityChip :severity="detail.incident.severity" />
          </div>
          <div class="col-6"><strong>種類:</strong> {{ detail.type_name }}</div>
          <div class="col-6"><strong>発見者:</strong> {{ detail.detector_name }}</div>
          <div class="col-6"><strong>発生個所:</strong> {{ detail.incident.location_name }}</div>
          <div class="col-6"><strong>問題管理番号:</strong> {{ detail.incident.problem_management_no || '—' }}</div>
          <div class="col-12"><strong>影響サービス:</strong> {{ detail.service_names?.join(', ') }}</div>
          <div class="col-12"><strong>影響顧客:</strong> {{ customerNames }}</div>
          <div class="col-12">
            <strong>説明:</strong>
            <div class="preserve-text q-mt-sm">{{ detail.incident.description }}</div>
          </div>
        </div>
      </q-card-section>
    </q-card>

    <q-card flat bordered class="q-mb-md" v-if="detail.investigation">
      <q-card-section>
        <div class="text-subtitle1">調査</div>
        <div v-if="investigationHasDistinctDetail" class="preserve-text q-mt-sm">
          <div class="text-weight-medium q-mb-xs">{{ detail.investigation.root_cause_summary }}</div>
          <div>{{ detail.investigation.investigation_detail }}</div>
        </div>
        <div v-else class="preserve-text q-mt-sm">
          {{ detail.investigation.investigation_detail }}
        </div>
      </q-card-section>
    </q-card>

    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="row items-center q-mb-sm">
          <div class="text-subtitle1">推奨手順書</div>
          <q-space />
          <q-btn flat dense icon="refresh" @click="loadRecommendations" :loading="recLoading" />
        </div>
        <div v-if="recommended.length" class="row q-col-gutter-sm">
          <div v-for="p in recommended" :key="p.procedure_id" class="col-12 col-md-6">
            <q-card bordered flat>
              <q-card-section>
                <div class="text-weight-medium">{{ p.title }}</div>
                <div class="text-caption">{{ p.procedure_id }} / 類似度 {{ p.score }}%</div>
                <div class="text-caption" v-if="p.success_rate != null">成功率 {{ p.success_rate }}%</div>
                <div class="row q-gutter-xs q-mt-sm">
                  <q-btn dense flat size="sm" label="詳細" :to="{ name: 'procedure-detail', params: { id: p.procedure_id } }" />
                  <q-btn dense color="primary" size="sm" label="適用" @click="applyProc(String(p.procedure_id))" />
                </div>
              </q-card-section>
            </q-card>
          </div>
        </div>
        <div v-else class="text-grey">推奨手順書はありません</div>
      </q-card-section>
    </q-card>

    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="text-subtitle1 q-mb-sm">類似インシデント</div>
        <q-list bordered separator v-if="similarIncidents.length">
          <q-item
            v-for="s in similarIncidents"
            :key="s.incident_id"
            clickable
            :to="{ name: 'detail', params: { id: s.incident_id } }"
          >
            <q-item-section>
              <q-item-label>{{ s.title }}</q-item-label>
              <q-item-label caption>
                {{ s.incident_id }} / 類似度 {{ s.score }}% / {{ s.status_label || s.status }}
              </q-item-label>
              <q-item-label caption v-if="s.applied_procedure_ids?.length">
                適用手順書: {{ s.applied_procedure_ids.join(', ') }}
              </q-item-label>
              <q-item-label caption v-if="s.response_summary">{{ s.response_summary }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
        <div v-else class="text-grey">類似インシデントはありません</div>
      </q-card-section>
    </q-card>

    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="row items-center q-mb-sm">
          <div class="text-subtitle1">紐づけ手順書</div>
          <q-space />
          <q-btn
            color="secondary"
            label="手順書を作成"
            :disable="detail.incident.status !== 'RESOLVED'"
            @click="createProcedure"
          >
            <q-tooltip v-if="detail.incident.status !== 'RESOLVED'">
              解決済みインシデントのみ作成できます
            </q-tooltip>
          </q-btn>
        </div>
        <q-list bordered separator v-if="linkedProcedures.length">
          <q-item v-for="lp in linkedProcedures" :key="lp.id">
            <q-item-section>
              <q-item-label>
                <router-link :to="{ name: 'procedure-detail', params: { id: lp.procedure_id } }">
                  {{ lp.title }} ({{ lp.procedure_id }})
                </router-link>
              </q-item-label>
              <q-item-label caption>{{ fmt(String(lp.applied_at)) }}</q-item-label>
              <div class="row q-gutter-xs q-mt-xs items-center">
                <span class="text-caption">成功:</span>
                <q-select
                  dense
                  outlined
                  :model-value="lp.was_successful"
                  :options="successOptions"
                  emit-value
                  map-options
                  style="min-width: 120px"
                  @update:model-value="(v) => v != null && saveSuccess(Number(lp.id), v)"
                />
                <q-btn
                  dense
                  flat
                  color="negative"
                  label="解除"
                  @click="confirmUnlink(Number(lp.id), String(lp.title))"
                />
              </div>
            </q-item-section>
          </q-item>
        </q-list>
        <div v-else class="text-grey">紐づけ手順書はありません</div>
      </q-card-section>
    </q-card>

    <q-card flat bordered>
      <q-card-section>
        <div class="text-subtitle1 q-mb-md">対応履歴</div>
        <q-list bordered separator>
          <q-item v-for="r in detail.responses" :key="r.response_id">
            <q-item-section>
              <q-item-label>{{ r.summary }}</q-item-label>
              <q-item-label caption>
                {{ r.response_type }} / {{ r.assignee_name }} / seq {{ r.sequence_no }}
              </q-item-label>
              <q-item-label caption>{{ fmt(r.started_at) }}</q-item-label>
              <div
                v-if="r.detail?.trim()"
                class="q-mt-sm markdown-body"
                v-html="renderMarkdown(r.detail)"
              />
              <div class="q-mt-sm">
                <q-btn dense flat size="sm" label="編集" @click="editResponse(r)" />
              </div>
            </q-item-section>
          </q-item>
        </q-list>
        <ResponseInlineForm
          class="q-mt-md"
          :incident-id="incidentId"
          :editing="editingResponse"
          @saved="load"
          @cancel="editingResponse = null"
        />
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import {
  applyProcedure,
  fetchIncidentDetail,
  fetchIncidentProcedures,
  fetchRecommendedProcedures,
  unlinkIncidentProcedure,
  updateProcedureSuccess,
} from '@/api/client'
import { buildSimilarIncidentsMessage, useChatSend } from '@/composables/useChatSend'
import { useTriageStart } from '@/composables/useTriageStart'
import { useChatStore } from '@/stores/chatStore'
import { useIncidentStore } from '@/stores/incidentStore'
import { useUiStore } from '@/stores/uiStore'
import { statusDisplayLabel } from '@/utils/incidentLabels'
import { renderMarkdown } from '@/utils/markdown'
import ResponseInlineForm from '@/components/ResponseInlineForm.vue'
import SeverityChip from '@/components/SeverityChip.vue'

const route = useRoute()
const router = useRouter()
const $q = useQuasar()
const incidentStore = useIncidentStore()
const chatStore = useChatStore()
const uiStore = useUiStore()
const { sendMessage } = useChatSend()
const { streaming } = storeToRefs(chatStore)
const incidentId = computed(() => String(route.params.id))
const detail = ref<Record<string, any> | null>(null)
const editingResponse = ref<Record<string, any> | null>(null)
const recommended = ref<Array<Record<string, any>>>([])
const similarIncidents = ref<Array<Record<string, any>>>([])
const linkedProcedures = ref<Array<Record<string, any>>>([])
const recLoading = ref(false)

const successOptions = [
  { label: '未入力', value: null },
  { label: 'はい', value: 1 },
  { label: 'いいえ', value: 0 },
]

const customerNames = computed(
  () => detail.value?.customers?.map((c: { customer_name: string }) => c.customer_name).join(', ') || 'なし',
)

const incidentStatusLabel = computed(() => {
  const inc = detail.value?.incident
  if (!inc) return ''
  return inc.status_label ?? statusDisplayLabel(inc.status)
})

const investigationHasDistinctDetail = computed(() => {
  const inv = detail.value?.investigation
  if (!inv) return false
  return inv.root_cause_summary !== inv.investigation_detail
})

function fmt(iso: string) {
  return new Date(iso).toLocaleString('ja-JP')
}

async function load() {
  detail.value = await fetchIncidentDetail(incidentId.value)
  incidentStore.contextIncidentId = incidentId.value
  editingResponse.value = null
  await loadRecommendations()
  linkedProcedures.value = await fetchIncidentProcedures(incidentId.value)
}

async function loadRecommendations() {
  recLoading.value = true
  try {
    const data = await fetchRecommendedProcedures(incidentId.value)
    recommended.value = data.recommended_procedures || []
    similarIncidents.value = data.similar_incidents || []
  } catch {
    recommended.value = []
    similarIncidents.value = []
  } finally {
    recLoading.value = false
  }
}

async function applyProc(procedureId: string) {
  try {
    await applyProcedure(incidentId.value, procedureId)
    $q.notify({ type: 'positive', message: '手順書を適用しました' })
    await load()
  } catch {
    $q.notify({ type: 'negative', message: '適用に失敗しました' })
  }
}

function createProcedure() {
  router.push({
    name: 'procedure-create',
    query: { from_incident: incidentId.value },
  })
}

async function saveSuccess(linkId: number, val: number | null) {
  if (val === null) return
  try {
    await updateProcedureSuccess(incidentId.value, linkId, val === 1)
    $q.notify({ type: 'positive', message: '成功可否を更新しました' })
    await load()
  } catch {
    $q.notify({ type: 'negative', message: '更新に失敗しました' })
  }
}

function confirmUnlink(linkId: number, title: string) {
  $q.dialog({
    title: '紐づけ解除',
    message: `「${title}」の適用記録を解除しますか？`,
    cancel: true,
    persistent: true,
  }).onOk(() => {
    void unlinkProcedure(linkId)
  })
}

async function unlinkProcedure(linkId: number) {
  try {
    await unlinkIncidentProcedure(incidentId.value, linkId)
    $q.notify({ type: 'positive', message: '紐づけを解除しました' })
    await load()
  } catch {
    $q.notify({ type: 'negative', message: '解除に失敗しました' })
  }
}

watch(
  incidentId,
  (id) => {
    incidentStore.contextIncidentId = id
  },
  { immediate: true },
)

function editResponse(r: Record<string, any>) {
  editingResponse.value = r
}

function findSimilarIncidents() {
  incidentStore.contextIncidentId = incidentId.value
  uiStore.openChatPanel()
  sendMessage(buildSimilarIncidentsMessage(incidentId.value))
}

watch(incidentId, load)
watch(() => incidentStore.detailReloadNonce, load)
onMounted(load)
useTriageStart(incidentId)
</script>

<style scoped>
.preserve-text {
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.severity-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: anywhere;
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
