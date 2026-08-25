<template>
  <q-card flat bordered>
    <q-card-section>
      <div class="text-h6">{{ isNew ? 'インシデント新規登録' : 'インシデント編集' }}</div>
      <q-form class="q-gutter-md q-mt-md" @submit.prevent="save">
        <q-input v-model="form.title" label="タイトル" outlined dense :rules="[req]" />
        <q-input v-model="form.description" label="説明" type="textarea" outlined dense :rules="[req]" />
        <q-expansion-item
          v-if="similarProcedures.length"
          icon="menu_book"
          label="類似手順書"
          header-class="text-primary"
        >
          <q-list dense bordered separator>
            <q-item
              v-for="p in similarProcedures"
              :key="p.procedure_id"
              clickable
              :to="{ name: 'procedure-detail', params: { id: p.procedure_id } }"
            >
              <q-item-section>
                <q-item-label>{{ p.title }}</q-item-label>
                <q-item-label caption>{{ p.procedure_id }} / 類似度 {{ p.score }}%</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-expansion-item>
        <q-select v-model="form.type_id" :options="typeOptions" label="種類" outlined dense emit-value map-options />
        <q-input v-model="form.occurred_at" label="発生日時" type="datetime-local" outlined dense />
        <div ref="locationInputAnchor">
          <q-input
            v-model="form.location_name"
            label="発生個所"
            outlined
            dense
            hint="ダブルクリックで候補から選択"
            @dblclick="openLocationMenu"
          />
        </div>
        <q-menu
          v-model="locationMenuOpen"
          :target="locationMenuTarget"
          anchor="bottom left"
          self="top left"
          no-parent-event
          transition-show="scale"
          transition-hide="scale"
        >
          <q-card class="location-picker-card">
            <q-card-section class="q-py-sm text-subtitle2">発生個所を選択</q-card-section>
            <q-separator />
            <q-list dense class="location-picker-list">
              <q-item
                v-for="name in locationOptions"
                :key="name"
                v-close-popup
                clickable
                @click="selectLocation(name)"
              >
                <q-item-section>{{ name }}</q-item-section>
              </q-item>
            </q-list>
          </q-card>
        </q-menu>
        <q-input v-model="form.problem_management_no" label="問題管理番号" outlined dense />
        <q-select
          v-model="form.affected_service_ids"
          :options="serviceOptions"
          label="影響サービス"
          multiple
          use-chips
          outlined
          dense
          emit-value
          map-options
        />
        <q-select v-model="form.status" :options="statusOptions" label="状態" outlined dense emit-value map-options />
        <q-select v-model="form.severity" :options="severityOptions" label="重要度" outlined dense emit-value map-options />
        <q-select
          v-model="form.detection_source"
          :options="detectionOptions"
          label="検知元"
          outlined
          dense
          emit-value
          map-options
        />
        <q-select
          v-model="form.detector_employee_id"
          :options="employeeOptions"
          label="検出者"
          outlined
          dense
          emit-value
          map-options
        />
        <q-select
          v-model="form.detector_department_id"
          :options="departmentOptions"
          label="検出部署"
          outlined
          dense
          emit-value
          map-options
        />
        <q-select
          v-model="form.customer_ids"
          :options="customerOptions"
          label="影響顧客"
          multiple
          use-chips
          outlined
          dense
          emit-value
          map-options
        />
        <div class="row justify-end">
          <q-btn type="submit" color="primary" label="保存" :loading="saving" />
        </div>
      </q-form>

      <div v-if="!isNew && responses.length" class="q-mt-lg">
        <div class="text-subtitle1">対応一覧（参照のみ）</div>
        <q-list bordered separator>
          <q-item v-for="r in responses" :key="r.response_id">
            <q-item-section>
              <q-item-label>{{ r.summary }}</q-item-label>
              <q-item-label caption>{{ r.response_type }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useQuasar } from 'quasar'
import { createIncident, fetchIncidentDetail, fetchMasters, fetchSimilarProcedures, updateIncident } from '@/api/client'
import { useOptimisticLockConflict } from '@/composables/useOptimisticLockConflict'
import { useAuthStore } from '@/stores/authStore'
import { formatApiError } from '@/utils/apiError'
import { getSettings } from './editDefaults'

const props = defineProps<{ incidentId: string | null; isNew: boolean }>()
const emit = defineEmits<{ saved: [id: string] }>()

const $q = useQuasar()
const auth = useAuthStore()
const { handleConflict } = useOptimisticLockConflict()

const saving = ref(false)
const rowVersion = ref(1)
const responses = ref<Array<Record<string, any>>>([])
const typeOptions = ref<Array<{ label: string; value: string }>>([])
const serviceOptions = ref<Array<{ label: string; value: string }>>([])
const customerOptions = ref<Array<{ label: string; value: string }>>([])
const employeeOptions = ref<Array<{ label: string; value: string }>>([])
const departmentOptions = ref<Array<{ label: string; value: string }>>([])
const locationOptions = ref<string[]>([])
const locationMenuOpen = ref(false)
const locationInputAnchor = ref<HTMLElement | null>(null)
const locationMenuTarget = computed(() => locationInputAnchor.value ?? undefined)
const similarProcedures = ref<Array<{ procedure_id: string; title: string; score: number }>>([])
let similarTimer: ReturnType<typeof setTimeout> | null = null

const form = reactive({
  title: '',
  description: '',
  type_id: 'ITYP-001',
  occurred_at: '',
  location_name: '',
  problem_management_no: '',
  affected_service_ids: ['SVC-001'] as string[],
  detector_employee_id: '',
  detector_department_id: '',
  severity: 'MEDIUM',
  status: 'OPEN',
  detection_source: 'OPS_MONITORING',
  related_event_id: null as string | null,
  customer_ids: [] as string[],
})

function applyDefaults() {
  const defaults = getSettings()
  form.occurred_at = defaults.occurredAtLocal
  form.detector_employee_id = defaults.operatorId
  form.detector_department_id = defaults.departmentId
}

const statusOptions = [
  { label: '未着手', value: 'OPEN' },
  { label: '対応中', value: 'IN_PROGRESS' },
  { label: '解決済み', value: 'RESOLVED' },
]
const severityOptions = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((v) => ({ label: v, value: v }))
const detectionOptions = [
  { label: '運用監視', value: 'OPS_MONITORING' },
  { label: '営業問合せ', value: 'SALES_INQUIRY' },
]

const req = (v: string) => !!v || '必須です'

watch(
  () => [form.title, form.description],
  () => {
    if (similarTimer) clearTimeout(similarTimer)
    similarTimer = setTimeout(async () => {
      const text = form.title + form.description
      if (text.length < 20) {
        similarProcedures.value = []
        return
      }
      try {
        similarProcedures.value = (await fetchSimilarProcedures(form.title, form.description)) as Array<{
          procedure_id: string
          title: string
          score: number
        }>
      } catch {
        similarProcedures.value = []
      }
    }, 300)
  },
)

onMounted(async () => {
  await auth.fetchMe().catch(() => {})
  const [types, services, customers, employees, departments] = await Promise.all([
    fetchMasters('incident-types'),
    fetchMasters('services'),
    fetchMasters('customers'),
    fetchMasters('employees'),
    fetchMasters('departments'),
  ])
  typeOptions.value = types.map((t) => ({ label: t.type_name, value: t.type_id }))
  serviceOptions.value = services.map((s) => ({ label: s.service_name, value: s.service_id }))
  customerOptions.value = customers.map((c) => ({ label: c.customer_name, value: c.customer_id }))
  employeeOptions.value = employees.map((e) => ({ label: e.employee_name, value: e.employee_id }))
  departmentOptions.value = departments.map((d) => ({ label: d.department_name, value: d.department_id }))

  if (props.isNew) {
    applyDefaults()
  } else if (props.incidentId) {
    await loadDetail()
  }
})

async function loadDetail() {
  if (!props.incidentId) return
  const detail = await fetchIncidentDetail(props.incidentId)
  const inc = detail.incident
  form.title = inc.title
  form.description = inc.description
  form.type_id = inc.type_id
  form.occurred_at = toLocal(inc.occurred_at)
  form.location_name = inc.location_name
  form.problem_management_no = inc.problem_management_no || ''
  form.affected_service_ids = inc.affected_service_ids || []
  form.detector_employee_id = inc.detector_employee_id
  form.detector_department_id = inc.detector_department_id
  form.severity = inc.severity
  form.status = inc.status
  form.detection_source = inc.detection_source
  form.related_event_id = inc.related_event_id
  form.customer_ids = detail.customers?.map((c: { customer_id: string }) => c.customer_id) || []
  responses.value = detail.responses || []
  rowVersion.value = Number(inc.row_version ?? 1)
}

function toLocal(iso: string) {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function openLocationMenu() {
  try {
    const items = await fetchMasters(
      `incident-type-locations?type_id=${encodeURIComponent(form.type_id)}`,
    )
    const names = items.map((row) => row.location_name).filter(Boolean)
    if (!names.length) {
      $q.notify({ type: 'info', message: 'この種類に登録された発生個所がありません' })
      return
    }
    locationOptions.value = names
    locationMenuOpen.value = true
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '発生個所の取得に失敗しました') })
  }
}

function selectLocation(name: string) {
  form.location_name = name
}

function toIso(local: string) {
  return new Date(local).toISOString()
}

async function save() {
  saving.value = true
  try {
    const body: Record<string, unknown> = {
      incident: {
        type_id: form.type_id,
        occurred_at: toIso(form.occurred_at),
        title: form.title,
        description: form.description,
        location_name: form.location_name,
        problem_management_no: form.problem_management_no || null,
        affected_service_ids: form.affected_service_ids,
        detector_employee_id: form.detector_employee_id,
        detector_department_id: form.detector_department_id,
        severity: form.severity,
        status: form.status,
        detection_source: form.detection_source,
        related_event_id: form.related_event_id,
      },
      customer_ids: form.customer_ids,
    }
    if (props.isNew) {
      const res = await createIncident(body)
      emit('saved', res.incident_id)
    } else if (props.incidentId) {
      body.row_version = rowVersion.value
      await updateIncident(props.incidentId, body)
      emit('saved', props.incidentId)
    }
  } catch (err: unknown) {
    const handled = await handleConflict(err, loadDetail)
    if (!handled) {
      $q.notify({ type: 'negative', message: formatApiError(err, '保存に失敗しました') })
    }
  } finally {
    saving.value = false
  }
}
</script>
