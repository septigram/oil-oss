<template>
  <q-page padding>
    <div class="text-h6 q-mb-md">Webhook API キー</div>
    <div class="row q-mb-md q-gutter-sm">
      <q-btn color="primary" label="新規生成" @click="openCreate" />
      <q-btn flat label="再読込" :loading="loading" @click="loadKeys" />
    </div>

    <q-table
      flat
      bordered
      :rows="keys"
      :columns="columns"
      row-key="key_id"
      :loading="loading"
      @row-click="(_evt, row) => openEdit(row)"
    />

    <q-dialog v-model="createDialogOpen" persistent>
      <q-card style="min-width: 420px; max-width: 90vw">
        <q-card-section>
          <div class="text-h6">API キー新規生成</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="createForm.name" label="名称" outlined dense />
          <q-select
            v-model="createForm.operator_employee_id"
            :options="employeeOptions"
            label="操作者（従業員）"
            outlined
            dense
            emit-value
            map-options
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="キャンセル" v-close-popup />
          <q-btn color="primary" label="生成" :loading="saving" @click="createKey" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="plainKeyDialogOpen" persistent>
      <q-card style="min-width: 480px; max-width: 90vw">
        <q-card-section>
          <div class="text-h6">API キーをコピーしてください</div>
          <div class="text-caption text-grey-7 q-mt-sm">この平文キーは再表示できません。</div>
        </q-card-section>
        <q-card-section>
          <q-input :model-value="generatedPlainKey" readonly outlined dense>
            <template #append>
              <q-btn flat dense icon="content_copy" @click="copyPlainKey" />
            </template>
          </q-input>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn color="primary" label="閉じる" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="editDialogOpen" persistent>
      <q-card style="min-width: 420px; max-width: 90vw">
        <q-card-section>
          <div class="text-h6">API キー編集 — {{ editForm.key_id }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="editForm.name" label="名称" outlined dense />
          <q-select
            v-model="editForm.operator_employee_id"
            :options="employeeOptions"
            label="操作者（従業員）"
            outlined
            dense
            emit-value
            map-options
          />
          <q-toggle v-model="editForm.is_active" label="有効" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat color="negative" label="無効化" @click="deactivateKey" />
          <q-btn flat label="キャンセル" v-close-popup />
          <q-btn color="primary" label="保存" :loading="saving" @click="saveEdit" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useQuasar, type QTableColumn } from 'quasar'
import {
  createWebhookApiKey,
  deleteWebhookApiKey,
  fetchMasters,
  fetchWebhookApiKeys,
  updateWebhookApiKey,
  type WebhookApiKeyListItem,
} from '@/api/client'
import { formatApiError } from '@/utils/apiError'

const $q = useQuasar()

const loading = ref(false)
const saving = ref(false)
const keys = ref<WebhookApiKeyListItem[]>([])
const employeeOptions = ref<Array<{ label: string; value: string }>>([])
const createDialogOpen = ref(false)
const editDialogOpen = ref(false)
const plainKeyDialogOpen = ref(false)
const generatedPlainKey = ref('')

const createForm = ref({ name: '', operator_employee_id: '' })
const editForm = ref({
  key_id: '',
  name: '',
  operator_employee_id: '',
  is_active: true,
})

const columns: QTableColumn[] = [
  { name: 'key_id', label: 'ID', field: 'key_id', align: 'left' },
  { name: 'name', label: '名称', field: 'name', align: 'left' },
  { name: 'operator_employee_id', label: '操作者', field: 'operator_employee_id', align: 'left' },
  { name: 'is_active', label: '有効', field: (row) => (row.is_active ? 'はい' : 'いいえ'), align: 'left' },
  { name: 'expires_at', label: '有効期限', field: (row) => row.expires_at ?? '無期限', align: 'left' },
]

async function loadKeys() {
  loading.value = true
  try {
    keys.value = await fetchWebhookApiKeys()
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '一覧の取得に失敗しました') })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.value = {
    name: '',
    operator_employee_id: employeeOptions.value[0]?.value ?? '',
  }
  createDialogOpen.value = true
}

function openEdit(row: WebhookApiKeyListItem) {
  editForm.value = {
    key_id: row.key_id,
    name: row.name,
    operator_employee_id: row.operator_employee_id,
    is_active: row.is_active,
  }
  editDialogOpen.value = true
}

async function createKey() {
  saving.value = true
  try {
    const result = await createWebhookApiKey({
      name: createForm.value.name.trim(),
      operator_employee_id: createForm.value.operator_employee_id,
    })
    generatedPlainKey.value = result.api_key
    createDialogOpen.value = false
    plainKeyDialogOpen.value = true
    await loadKeys()
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '生成に失敗しました') })
  } finally {
    saving.value = false
  }
}

async function saveEdit() {
  saving.value = true
  try {
    await updateWebhookApiKey(editForm.value.key_id, {
      name: editForm.value.name.trim(),
      operator_employee_id: editForm.value.operator_employee_id,
      is_active: editForm.value.is_active,
    })
    editDialogOpen.value = false
    await loadKeys()
    $q.notify({ type: 'positive', message: '更新しました' })
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '更新に失敗しました') })
  } finally {
    saving.value = false
  }
}

async function deactivateKey() {
  saving.value = true
  try {
    await deleteWebhookApiKey(editForm.value.key_id)
    editDialogOpen.value = false
    await loadKeys()
    $q.notify({ type: 'positive', message: '無効化しました' })
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '無効化に失敗しました') })
  } finally {
    saving.value = false
  }
}

async function copyPlainKey() {
  try {
    await navigator.clipboard.writeText(generatedPlainKey.value)
    $q.notify({ type: 'positive', message: 'コピーしました' })
  } catch {
    $q.notify({ type: 'warning', message: 'コピーに失敗しました' })
  }
}

onMounted(async () => {
  const employees = await fetchMasters('employees')
  employeeOptions.value = employees.map((e) => ({
    label: `${e.employee_name} (${e.employee_id})`,
    value: e.employee_id,
  }))
  await loadKeys()
})
</script>
