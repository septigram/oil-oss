<template>
  <q-page padding>
    <div class="text-h6 q-mb-md">ユーザ管理</div>
    <div class="row q-mb-md q-gutter-sm">
      <q-btn color="primary" label="新規ユーザ" @click="openCreate" />
      <q-btn flat label="再読込" :loading="loading" @click="loadUsers" />
    </div>

    <q-table
      flat
      bordered
      :rows="users"
      :columns="columns"
      row-key="user_id"
      :loading="loading"
      @row-click="(_evt, row) => openEdit(row)"
    />

    <q-dialog v-model="dialogOpen" persistent>
      <q-card style="min-width: 420px; max-width: 90vw">
        <q-card-section>
          <div class="text-h6">{{ dialogMode === 'create' ? 'ユーザ新規登録' : 'ユーザ編集' }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <template v-if="dialogMode === 'create'">
            <q-select
              v-model="form.employee_id"
              :options="employeeOptions"
              label="従業員"
              outlined
              dense
              emit-value
              map-options
            />
            <q-input v-model="form.login_name" label="ログイン ID" outlined dense />
            <q-input v-model="form.password" label="初期パスワード" type="password" outlined dense />
          </template>
          <template v-else>
            <div class="text-body2">{{ form.employee_name }} ({{ form.login_name }})</div>
            <q-toggle v-model="form.is_active" label="有効" />
            <q-input v-model="form.password" label="新しいパスワード（変更時のみ）" type="password" outlined dense clearable />
          </template>
          <q-select
            v-model="form.roles"
            :options="roleOptions"
            label="ロール"
            multiple
            use-chips
            outlined
            dense
            emit-value
            map-options
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="キャンセル" v-close-popup />
          <q-btn color="primary" label="保存" :loading="saving" @click="save" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useQuasar, type QTableColumn } from 'quasar'
import {
  createAdminUser,
  fetchAdminUsers,
  fetchMasters,
  updateAdminUser,
  updateAdminUserRoles,
  type AdminUserListItem,
} from '@/api/client'
import { useOptimisticLockConflict } from '@/composables/useOptimisticLockConflict'
import { formatApiError } from '@/utils/apiError'

const $q = useQuasar()
const { handleConflict } = useOptimisticLockConflict()

const loading = ref(false)
const saving = ref(false)
const dialogOpen = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const users = ref<AdminUserListItem[]>([])
const employeeOptions = ref<Array<{ label: string; value: string }>>([])

const form = ref({
  user_id: '',
  employee_id: '',
  employee_name: '',
  login_name: '',
  password: '',
  is_active: true,
  roles: [] as string[],
  row_version: 1,
})

const roleOptions = [
  { label: '管理者', value: 'ADMIN' },
  { label: 'オペレータ', value: 'OPERATOR' },
  { label: '閲覧者', value: 'VIEWER' },
]

const columns: QTableColumn[] = [
  { name: 'login_name', label: 'ログイン ID', field: 'login_name', align: 'left' },
  { name: 'employee_name', label: '従業員名', field: 'employee_name', align: 'left' },
  { name: 'roles', label: 'ロール', field: (row) => row.roles.join(', '), align: 'left' },
  { name: 'is_active', label: '有効', field: (row) => (row.is_active ? 'はい' : 'いいえ'), align: 'left' },
  { name: 'row_version', label: '版', field: 'row_version', align: 'right' },
]

async function loadUsers() {
  loading.value = true
  try {
    users.value = await fetchAdminUsers()
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, 'ユーザ一覧の取得に失敗しました') })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialogMode.value = 'create'
  form.value = {
    user_id: '',
    employee_id: employeeOptions.value[0]?.value ?? '',
    employee_name: '',
    login_name: '',
    password: '',
    is_active: true,
    roles: ['OPERATOR'],
    row_version: 1,
  }
  dialogOpen.value = true
}

function openEdit(row: AdminUserListItem) {
  dialogMode.value = 'edit'
  form.value = {
    user_id: row.user_id,
    employee_id: row.employee_id,
    employee_name: row.employee_name,
    login_name: row.login_name,
    password: '',
    is_active: row.is_active,
    roles: [...row.roles],
    row_version: row.row_version,
  }
  dialogOpen.value = true
}

async function reloadAfterConflict() {
  dialogOpen.value = false
  await loadUsers()
}

async function save() {
  saving.value = true
  try {
    if (dialogMode.value === 'create') {
      await createAdminUser({
        employee_id: form.value.employee_id,
        login_name: form.value.login_name.trim(),
        password: form.value.password,
        roles: form.value.roles,
      })
      $q.notify({ type: 'positive', message: 'ユーザを登録しました' })
    } else {
      const updateBody: { row_version: number; is_active?: boolean; password?: string } = {
        row_version: form.value.row_version,
        is_active: form.value.is_active,
      }
      if (form.value.password.trim()) {
        updateBody.password = form.value.password
      }
      const updated = await updateAdminUser(form.value.user_id, updateBody)
      await updateAdminUserRoles(form.value.user_id, {
        row_version: updated.row_version,
        roles: form.value.roles,
      })
      $q.notify({ type: 'positive', message: 'ユーザを更新しました' })
    }
    dialogOpen.value = false
    await loadUsers()
  } catch (err: unknown) {
    const handled = await handleConflict(err, reloadAfterConflict)
    if (!handled) {
      $q.notify({ type: 'negative', message: formatApiError(err, '保存に失敗しました') })
    }
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const employees = await fetchMasters('employees')
  employeeOptions.value = employees.map((e) => ({
    label: `${e.employee_name} (${e.employee_id})`,
    value: e.employee_id,
  }))
  await loadUsers()
})
</script>
