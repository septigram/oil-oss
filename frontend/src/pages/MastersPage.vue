<template>
  <q-page padding>
    <div class="text-h6 q-mb-md">マスター管理</div>
    <q-tabs v-model="tab" dense align="left" class="text-primary" active-color="primary" indicator-color="primary">
      <q-tab name="incident-types" label="インシデント種類" />
      <q-tab name="incident-type-locations" label="発生個所" />
      <q-tab name="customers" label="顧客" />
      <q-tab name="services" label="サービス" />
      <q-tab name="departments" label="部署" />
      <q-tab name="employees" label="従業員" />
    </q-tabs>
    <q-separator />

    <div v-if="tab === 'incident-type-locations'" class="q-my-md">
      <q-select
        v-model="locationTypeId"
        :options="typeOptions"
        label="種類"
        outlined
        dense
        emit-value
        map-options
        style="max-width: 320px"
        @update:model-value="loadLocations"
      />
    </div>

    <div class="row q-my-md q-gutter-sm">
      <q-btn color="primary" label="新規" @click="openCreate(tab)" />
      <q-btn flat label="再読込" :loading="loading" @click="loadTab" />
    </div>

    <q-table
      flat
      bordered
      :rows="currentRows"
      :columns="currentColumns"
      :loading="loading"
      :row-key="rowKey"
      @row-click="(_evt, row) => openEdit(tab, row)"
    />

    <q-dialog v-model="dialogOpen" persistent>
      <q-card style="min-width: 420px; max-width: 90vw">
        <q-card-section>
          <div class="text-h6">{{ dialogMode === 'create' ? '新規登録' : '編集' }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <template v-if="dialogResource === 'incident-types'">
            <q-input v-if="dialogMode === 'create'" v-model="form.type_id" label="種類 ID" outlined dense />
            <q-input v-model="form.type_name" label="種類名" outlined dense />
            <q-input v-model.number="form.avg_detection_minutes" label="平均検知時間（分）" type="number" outlined dense />
            <q-select v-model="form.severity_default" :options="severityOptions" label="デフォルト重要度" outlined dense emit-value map-options />
            <q-select v-model="form.detection_source" :options="detectionOptions" label="検知元" outlined dense emit-value map-options />
          </template>
          <template v-else-if="dialogResource === 'incident-type-locations'">
            <q-select v-model="form.type_id" :options="typeOptions" label="種類" outlined dense emit-value map-options />
            <q-input v-model="form.location_name" label="発生個所" outlined dense />
          </template>
          <template v-else-if="dialogResource === 'customers'">
            <q-input v-if="dialogMode === 'create'" v-model="form.customer_id" label="顧客 ID" outlined dense />
            <q-input v-model="form.customer_name" label="顧客名" outlined dense />
            <q-input v-model="form.industry_segment" label="業種" outlined dense />
          </template>
          <template v-else-if="dialogResource === 'services'">
            <q-input v-if="dialogMode === 'create'" v-model="form.service_id" label="サービス ID" outlined dense />
            <q-input v-model="form.service_name" label="サービス名" outlined dense />
            <q-input v-model="form.description" label="説明" type="textarea" outlined dense autogrow />
          </template>
          <template v-else-if="dialogResource === 'departments'">
            <q-input v-model="form.department_id" label="部署 ID" outlined dense :readonly="dialogMode === 'edit'" />
            <q-input v-model="form.department_name" label="部署名" outlined dense />
          </template>
          <template v-else-if="dialogResource === 'employees'">
            <q-input v-if="dialogMode === 'create'" v-model="form.employee_id" label="従業員 ID（空欄で自動採番）" outlined dense />
            <q-input v-model="form.employee_name" label="氏名" outlined dense />
            <q-select v-model="form.department_id" :options="departmentOptions" label="所属部署" outlined dense emit-value map-options />
          </template>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="キャンセル" v-close-popup />
          <q-btn color="primary" label="保存" :loading="saving" @click="saveDialog" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useQuasar, type QTableColumn } from 'quasar'
import { createMaster, fetchMasters, updateMaster } from '@/api/client'
import { useOptimisticLockConflict } from '@/composables/useOptimisticLockConflict'
import { formatApiError } from '@/utils/apiError'

type MasterTab =
  | 'incident-types'
  | 'incident-type-locations'
  | 'customers'
  | 'services'
  | 'departments'
  | 'employees'

const $q = useQuasar()
const { handleConflict } = useOptimisticLockConflict()

const tab = ref<MasterTab>('incident-types')
const loading = ref(false)
const saving = ref(false)
const dialogOpen = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const dialogResource = ref<MasterTab>('incident-types')
type MasterForm = {
  type_id?: string
  type_name?: string
  avg_detection_minutes?: number
  severity_default?: string
  detection_source?: string
  location_name?: string
  customer_id?: string
  customer_name?: string
  industry_segment?: string
  service_id?: string
  service_name?: string
  description?: string
  department_id?: string
  department_name?: string
  employee_id?: string
  employee_name?: string
  row_version?: number
}

const form = reactive<MasterForm>({})
const editKey = ref('')

const incidentTypes = ref<Array<Record<string, unknown>>>([])
const locations = ref<Array<Record<string, unknown>>>([])
const customers = ref<Array<Record<string, unknown>>>([])
const services = ref<Array<Record<string, unknown>>>([])
const departments = ref<Array<Record<string, unknown>>>([])
const employees = ref<Array<Record<string, unknown>>>([])
const locationTypeId = ref('ITYP-001')

const severityOptions = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((v) => ({ label: v, value: v }))
const detectionOptions = [
  { label: '運用監視', value: 'OPS_MONITORING' },
  { label: '営業問合せ', value: 'SALES_INQUIRY' },
]

const typeOptions = computed(() =>
  incidentTypes.value.map((t) => ({ label: String(t.type_name), value: String(t.type_id) })),
)
const departmentOptions = computed(() =>
  departments.value.map((d) => ({ label: String(d.department_name), value: String(d.department_id) })),
)

const incidentTypeColumns: QTableColumn[] = [
  { name: 'type_id', label: 'ID', field: 'type_id', align: 'left' },
  { name: 'type_name', label: '種類名', field: 'type_name', align: 'left' },
  { name: 'avg_detection_minutes', label: '平均検知（分）', field: 'avg_detection_minutes', align: 'right' },
  { name: 'severity_default', label: '重要度', field: 'severity_default', align: 'left' },
  { name: 'row_version', label: '版', field: 'row_version', align: 'right' },
]

const locationColumns: QTableColumn[] = [
  { name: 'type_id', label: '種類 ID', field: 'type_id', align: 'left' },
  { name: 'location_name', label: '発生個所', field: 'location_name', align: 'left' },
  { name: 'row_version', label: '版', field: 'row_version', align: 'right' },
]

const customerColumns: QTableColumn[] = [
  { name: 'customer_id', label: 'ID', field: 'customer_id', align: 'left' },
  { name: 'customer_name', label: '顧客名', field: 'customer_name', align: 'left' },
  { name: 'industry_segment', label: '業種', field: 'industry_segment', align: 'left' },
  { name: 'row_version', label: '版', field: 'row_version', align: 'right' },
]

const serviceColumns: QTableColumn[] = [
  { name: 'service_id', label: 'ID', field: 'service_id', align: 'left' },
  { name: 'service_name', label: 'サービス名', field: 'service_name', align: 'left' },
  { name: 'description', label: '説明', field: 'description', align: 'left' },
  { name: 'row_version', label: '版', field: 'row_version', align: 'right' },
]

const departmentColumns: QTableColumn[] = [
  { name: 'department_id', label: 'ID', field: 'department_id', align: 'left' },
  { name: 'department_name', label: '部署名', field: 'department_name', align: 'left' },
  { name: 'row_version', label: '版', field: 'row_version', align: 'right' },
]

const employeeColumns: QTableColumn[] = [
  { name: 'employee_id', label: 'ID', field: 'employee_id', align: 'left' },
  { name: 'employee_name', label: '氏名', field: 'employee_name', align: 'left' },
  { name: 'department_id', label: '部署 ID', field: 'department_id', align: 'left' },
  { name: 'row_version', label: '版', field: 'row_version', align: 'right' },
]

const columnMap: Record<MasterTab, QTableColumn[]> = {
  'incident-types': incidentTypeColumns,
  'incident-type-locations': locationColumns,
  customers: customerColumns,
  services: serviceColumns,
  departments: departmentColumns,
  employees: employeeColumns,
}

const currentColumns = computed(() => columnMap[tab.value])
const currentRows = computed(() => {
  switch (tab.value) {
    case 'incident-types':
      return incidentTypes.value
    case 'incident-type-locations':
      return locations.value
    case 'customers':
      return customers.value
    case 'services':
      return services.value
    case 'departments':
      return departments.value
    case 'employees':
      return employees.value
    default:
      return []
  }
})

function rowKey(row: Record<string, unknown>) {
  return idPathFor(tab.value, row)
}

function resetForm(resource: MasterTab) {
  Object.keys(form).forEach((k) => delete form[k as keyof MasterForm])
  switch (resource) {
    case 'incident-types':
      Object.assign(form, { type_id: '', type_name: '', avg_detection_minutes: 60, severity_default: 'MEDIUM', detection_source: 'OPS_MONITORING' })
      break
    case 'incident-type-locations':
      Object.assign(form, { type_id: locationTypeId.value, location_name: '' })
      break
    case 'customers':
      Object.assign(form, { customer_id: '', customer_name: '', industry_segment: '' })
      break
    case 'services':
      Object.assign(form, { service_id: '', service_name: '', description: '' })
      break
    case 'departments':
      Object.assign(form, { department_id: '', department_name: '' })
      break
    case 'employees':
      Object.assign(form, { employee_id: '', employee_name: '', department_id: departmentOptions.value[0]?.value ?? '' })
      break
  }
}

function openCreate(resource: MasterTab) {
  dialogResource.value = resource
  dialogMode.value = 'create'
  resetForm(resource)
  editKey.value = ''
  dialogOpen.value = true
}

function openEdit(resource: MasterTab, row: Record<string, unknown>) {
  dialogResource.value = resource
  dialogMode.value = 'edit'
  resetForm(resource)
  Object.assign(form, row as MasterForm)
  editKey.value = idPathFor(resource, row)
  dialogOpen.value = true
}

function idPathFor(resource: MasterTab, row: Record<string, unknown>): string {
  switch (resource) {
    case 'incident-types':
      return String(row.type_id)
    case 'incident-type-locations':
      return `${encodeURIComponent(String(row.type_id))}/${encodeURIComponent(String(row.location_name))}`
    case 'customers':
      return String(row.customer_id)
    case 'services':
      return String(row.service_id)
    case 'departments':
      return String(row.department_id)
    case 'employees':
      return String(row.employee_id)
    default:
      return ''
  }
}

async function loadLocations() {
  loading.value = true
  try {
    locations.value = await fetchMasters(
      `incident-type-locations?type_id=${encodeURIComponent(locationTypeId.value)}`,
    )
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '発生個所の取得に失敗しました') })
  } finally {
    loading.value = false
  }
}

async function loadTab() {
  loading.value = true
  try {
    switch (tab.value) {
      case 'incident-types':
        incidentTypes.value = await fetchMasters('incident-types')
        break
      case 'customers':
        customers.value = await fetchMasters('customers')
        break
      case 'services':
        services.value = await fetchMasters('services')
        break
      case 'departments':
        departments.value = await fetchMasters('departments')
        break
      case 'employees':
        employees.value = await fetchMasters('employees')
        break
      case 'incident-type-locations':
        await loadLocations()
        break
    }
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, 'マスターの取得に失敗しました') })
  } finally {
    loading.value = false
  }
}

async function reloadAfterConflict() {
  dialogOpen.value = false
  await loadTab()
}

async function saveDialog() {
  saving.value = true
  const resource = dialogResource.value
  try {
    if (dialogMode.value === 'create') {
      await createMaster(resource, { ...form })
      $q.notify({ type: 'positive', message: '登録しました' })
    } else {
      await updateMaster(resource, editKey.value, { ...form })
      $q.notify({ type: 'positive', message: '更新しました' })
    }
    dialogOpen.value = false
    await loadTab()
  } catch (err: unknown) {
    const handled = await handleConflict(err, reloadAfterConflict)
    if (!handled) {
      $q.notify({ type: 'negative', message: formatApiError(err, '保存に失敗しました') })
    }
  } finally {
    saving.value = false
  }
}

watch(tab, () => {
  loadTab()
})

onMounted(async () => {
  incidentTypes.value = await fetchMasters('incident-types')
  departments.value = await fetchMasters('departments')
  await loadTab()
})
</script>
