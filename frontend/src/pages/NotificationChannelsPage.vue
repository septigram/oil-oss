<template>
  <q-page padding>
    <div class="text-h6 q-mb-md">通知チャネル</div>
    <div class="row q-mb-md q-gutter-sm">
      <q-btn color="primary" label="新規チャネル" @click="openCreate" />
      <q-btn flat label="再読込" :loading="loading" @click="loadChannels" />
    </div>

    <q-table
      flat
      bordered
      :rows="channels"
      :columns="columns"
      row-key="channel_id"
      :loading="loading"
      @row-click="(_evt, row) => openEdit(row)"
    />

    <q-dialog v-model="dialogOpen" persistent>
      <q-card style="min-width: 480px; max-width: 90vw">
        <q-card-section>
          <div class="text-h6">{{ dialogMode === 'create' ? '通知チャネル新規' : '通知チャネル編集' }}</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="form.name" label="名称" outlined dense />
          <q-input v-model="form.webhook_url" label="Slack Incoming Webhook URL" outlined dense />
          <q-select
            v-model="form.type_ids"
            :options="typeOptions"
            label="対象インシデント種類"
            multiple
            use-chips
            outlined
            dense
            emit-value
            map-options
          />
          <q-toggle v-model="form.is_active" label="有効" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            v-if="dialogMode === 'edit'"
            flat
            color="negative"
            label="削除"
            @click="removeChannel"
          />
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
  createNotificationChannel,
  deleteNotificationChannel,
  fetchMasters,
  fetchNotificationChannels,
  updateNotificationChannel,
  type NotificationChannelItem,
} from '@/api/client'
import { useOptimisticLockConflict } from '@/composables/useOptimisticLockConflict'
import { formatApiError } from '@/utils/apiError'

const $q = useQuasar()
const { handleConflict } = useOptimisticLockConflict()

const loading = ref(false)
const saving = ref(false)
const dialogOpen = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const channels = ref<NotificationChannelItem[]>([])
const typeOptions = ref<Array<{ label: string; value: string }>>([])

const form = ref({
  channel_id: '',
  name: '',
  webhook_url: '',
  type_ids: [] as string[],
  is_active: true,
  row_version: 1,
})

const columns: QTableColumn[] = [
  { name: 'channel_id', label: 'ID', field: 'channel_id', align: 'left' },
  { name: 'name', label: '名称', field: 'name', align: 'left' },
  { name: 'type_ids', label: '対象種類', field: (row) => row.type_ids.join(', '), align: 'left' },
  { name: 'is_active', label: '有効', field: (row) => (row.is_active ? 'はい' : 'いいえ'), align: 'left' },
]

async function loadChannels() {
  loading.value = true
  try {
    channels.value = await fetchNotificationChannels()
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '一覧の取得に失敗しました') })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialogMode.value = 'create'
  form.value = {
    channel_id: '',
    name: '',
    webhook_url: '',
    type_ids: [],
    is_active: true,
    row_version: 1,
  }
  dialogOpen.value = true
}

function openEdit(row: NotificationChannelItem) {
  dialogMode.value = 'edit'
  form.value = {
    channel_id: row.channel_id,
    name: row.name,
    webhook_url: row.webhook_url,
    type_ids: [...row.type_ids],
    is_active: row.is_active,
    row_version: row.row_version,
  }
  dialogOpen.value = true
}

async function reloadAfterConflict() {
  dialogOpen.value = false
  await loadChannels()
}

async function save() {
  saving.value = true
  try {
    if (dialogMode.value === 'create') {
      await createNotificationChannel({
        name: form.value.name.trim(),
        webhook_url: form.value.webhook_url.trim(),
        type_ids: form.value.type_ids,
        is_active: form.value.is_active,
      })
      $q.notify({ type: 'positive', message: 'チャネルを登録しました' })
    } else {
      await updateNotificationChannel(form.value.channel_id, {
        name: form.value.name.trim(),
        webhook_url: form.value.webhook_url.trim(),
        type_ids: form.value.type_ids,
        is_active: form.value.is_active,
        row_version: form.value.row_version,
      })
      $q.notify({ type: 'positive', message: 'チャネルを更新しました' })
    }
    dialogOpen.value = false
    await loadChannels()
  } catch (err: unknown) {
    const handled = await handleConflict(err, reloadAfterConflict)
    if (!handled) {
      $q.notify({ type: 'negative', message: formatApiError(err, '保存に失敗しました') })
    }
  } finally {
    saving.value = false
  }
}

async function removeChannel() {
  saving.value = true
  try {
    await deleteNotificationChannel(form.value.channel_id)
    dialogOpen.value = false
    await loadChannels()
    $q.notify({ type: 'positive', message: '削除しました' })
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, '削除に失敗しました') })
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const types = await fetchMasters('incident-types')
  typeOptions.value = types.map((t) => ({
    label: `${t.type_name} (${t.type_id})`,
    value: t.type_id,
  }))
  await loadChannels()
})
</script>
