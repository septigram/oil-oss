<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="text-white" :class="serverReachable ? 'bg-primary' : 'bg-negative'">
      <q-toolbar>
        <q-btn
          flat
          dense
          round
          icon="menu"
          class="lt-md"
          @click="leftDrawerOpen = !leftDrawerOpen"
        />
        <q-toolbar-title>
          <router-link :to="{ name: 'list' }" class="app-title-link">
            Ops Incident Ledger
            <span class="subtitle">powered by Tsurugi</span>
            <span class="version">{{ version }}</span>
          </router-link>
          <span v-if="!serverReachable" class="server-error-msg">サーバに接続できません</span>
        </q-toolbar-title>
        <PanelSwitchButton v-model="uiStore.showQuickFilter" variant="l" label="クイックフィルタ" />
        <PanelSwitchButton v-model="uiStore.showChat" variant="r" label="AIチャット" />
        <PanelSwitchButton v-model="uiStore.showLogPanel" variant="b" label="サーバーログ" />
        <q-btn
          v-if="auth.isAdmin || auth.isOperator"
          flat
          dense
          round
          icon="settings"
          class="gt-sm q-mr-xs"
          aria-label="管理"
        >
          <q-menu anchor="bottom right" self="top right">
            <q-list dense style="min-width: 180px">
              <q-item v-if="auth.isAdmin" clickable v-close-popup :to="{ name: 'masters' }">
                <q-item-section>マスター</q-item-section>
              </q-item>
              <q-item v-if="auth.isAdmin" clickable v-close-popup :to="{ name: 'admin-users' }">
                <q-item-section>ユーザ</q-item-section>
              </q-item>
              <q-item v-if="auth.isAdmin" clickable v-close-popup :to="{ name: 'admin-webhook-api-keys' }">
                <q-item-section>Webhook API キー</q-item-section>
              </q-item>
              <q-item
                v-if="auth.isAdmin || auth.isOperator"
                clickable
                v-close-popup
                :to="{ name: 'notification-channels' }"
              >
                <q-item-section>通知チャネル</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
        <div class="q-mr-md text-caption" v-if="uiConfig">
          基準日: {{ uiConfig.reference_date }} ({{ uiConfig.reference_date_mode }})
        </div>
        <div class="text-caption q-mr-sm">{{ operatorLabel }}</div>
        <q-btn
          v-if="auth.authEnabled"
          flat
          dense
          no-caps
          label="ログアウト"
          class="gt-sm q-mr-sm"
          :loading="auth.loading"
          @click="doLogout"
        />
        <q-btn
          flat
          dense
          no-caps
          label="サーバーログ"
          class="lt-md q-mr-xs"
          :text-color="uiStore.showLogPanel ? 'white' : 'grey-4'"
          @click="uiStore.showLogPanel = !uiStore.showLogPanel"
        />
        <q-btn
          flat
          dense
          round
          icon="chat"
          class="lt-md"
          @click="rightDrawerOpen = !rightDrawerOpen"
        />
      </q-toolbar>
    </q-header>

    <q-drawer v-model="leftDrawerOpen" bordered class="lt-md" v-if="uiStore.showQuickFilter">
      <LeftPanelNav @quick="applyQuick" @navigate="applyNavigate" />
    </q-drawer>
    <q-drawer
      v-model="rightDrawerOpen"
      side="right"
      bordered
      :width="chatPanelWidthPx"
      class="lt-md"
      v-if="uiStore.showChat"
    >
      <ChatPanel />
    </q-drawer>

    <q-page-container>
      <div class="workspace">
        <div class="body-row row no-wrap">
          <aside v-show="uiStore.showQuickFilter" class="left-panel gt-sm">
            <LeftPanelNav @quick="applyQuick" @navigate="applyNavigate" />
          </aside>
          <main class="col main-panel">
            <router-view />
          </main>
          <aside
            v-show="uiStore.showChat"
            class="right-panel gt-sm"
            :style="{ width: `${chatPanelWidthPx}px` }"
          >
            <div
              class="resize-handle"
              role="separator"
              aria-orientation="vertical"
              aria-label="AIチャット幅を変更"
              @mousedown="startChatResize"
            />
            <ChatPanel />
          </aside>
        </div>
        <div v-show="uiStore.showLogPanel" class="log-panel">
          <LogPanel />
        </div>
      </div>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useQuasar } from 'quasar'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { fetchUiConfig, type SearchParams, type UiConfig } from '@/api/client'
import { useChatPanelResize } from '@/composables/useChatPanelResize'
import { useIncidentStore, INCIDENT_LIST_PAGE_SIZE } from '@/stores/incidentStore'
import { useAuthStore } from '@/stores/authStore'
import { useUiStore } from '@/stores/uiStore'
import ChatPanel from '@/components/ChatPanel.vue'
import LeftPanelNav from '@/components/LeftPanelNav.vue'
import LogPanel from '@/components/LogPanel.vue'
import PanelSwitchButton from '@/components/PanelSwitchButton.vue'
import { monthRange } from '@/utils/dateRange'

const version = 'v0.26.705'
const $q = useQuasar()
const router = useRouter()
const incidentStore = useIncidentStore()
const auth = useAuthStore()
const uiStore = useUiStore()
const { chatPanelWidthPx, serverReachable } = storeToRefs(uiStore)
const { startResize: startChatResize } = useChatPanelResize(chatPanelWidthPx)
const leftDrawerOpen = ref(false)
const rightDrawerOpen = ref(false)
const uiConfig = ref<UiConfig | null>(null)

const operatorLabel = computed(() => {
  if (auth.displayName) return auth.displayName
  return uiConfig.value?.operator_name ?? ''
})

async function doLogout() {
  await auth.logout()
  if (auth.authEnabled) {
    router.push({ name: 'login' })
  }
}

watch(
  () => uiStore.showQuickFilter,
  (visible) => {
    if (!visible) leftDrawerOpen.value = false
  },
)

watch(
  () => uiStore.showChat,
  (visible) => {
    if (!visible) rightDrawerOpen.value = false
  },
)

watch(
  () => uiStore.chatPanelOpenNonce,
  () => {
    // デスクトップ (md 以上) は右パネルに表示するため、ドロワーは開かない
    if ($q.screen.lt.md) {
      rightDrawerOpen.value = true
    }
  },
)

function onWindowResize() {
  uiStore.setChatPanelWidth(uiStore.chatPanelWidthPx)
}

onMounted(async () => {
  uiStore.resetChatPanelWidth()
  window.addEventListener('resize', onWindowResize)
  await auth.initialize()
  uiConfig.value = await fetchUiConfig()
})

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize)
})

function applyNavigate(target: 'incidentList' | 'procedureList') {
  leftDrawerOpen.value = false
  if (target === 'incidentList') {
    router.push({ name: 'list' })
  } else {
    router.push({ name: 'procedure-list' })
  }
}

function applyQuick(filter: 'thisMonth' | 'lastMonth' | 'unresolved') {
  if (!uiConfig.value) return
  const ref = uiConfig.value.reference_date
  const params: SearchParams = { page: 1, page_size: INCIDENT_LIST_PAGE_SIZE, quick: filter, rag: false }
  if (filter === 'thisMonth') {
    const { from, to } = monthRange(ref, 0)
    params.occurred_from = from
    params.occurred_to = to
  } else if (filter === 'lastMonth') {
    const { from, to } = monthRange(ref, -1)
    params.occurred_from = from
    params.occurred_to = to
  } else {
    params.status = ['OPEN', 'IN_PROGRESS']
  }
  incidentStore.searchParams = params
  leftDrawerOpen.value = false
  router.push({ name: 'list' })
}
</script>

<style scoped>
.workspace {
  height: calc(100vh - 50px);
  display: flex;
  flex-direction: column;
}

.body-row {
  flex: 1;
  min-height: 0;
}

.left-panel {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid rgba(0, 0, 0, 0.12);
  background: #fafafa;
  overflow: auto;
}

.right-panel {
  position: relative;
  flex-shrink: 0;
  border-left: 1px solid rgba(0, 0, 0, 0.12);
  background: #fafafa;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 6px;
  margin-left: -3px;
  cursor: col-resize;
  z-index: 2;
  touch-action: none;
}

.resize-handle:hover,
.resize-handle:active {
  background: rgba(25, 118, 210, 0.15);
}

.main-panel {
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

.log-panel {
  height: 30vh;
  flex-shrink: 0;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
  background: #f5f5f5;
  overflow: hidden;
}

.logo-icon {
  width: 48px;
  vertical-align: middle;
}

.subtitle {
  font-size: small;
  margin-right: 1rem;
}

.version {
  font-size: small;
  color: #ccc;
}

.app-title-link {
  color: inherit;
  text-decoration: none;
}

.app-title-link:hover {
  opacity: 0.85;
}

.server-error-msg {
  margin-left: 12px;
  font-size: small;
  font-weight: 600;
  color: #fff;
}

</style>
