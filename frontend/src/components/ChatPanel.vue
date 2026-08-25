<template>
  <div class="chat-panel column">
    <div class="row items-center q-mb-sm no-wrap chat-header-row">
      <div class="row items-center col-auto chat-title">
        <img :src="aiChatIcon" alt="" class="chat-title__icon" aria-hidden="true" />
        <div class="text-subtitle2">AI チャット</div>
      </div>
      <q-select
        v-model="selectedLlmKey"
        :options="llmOptions"
        dense
        outlined
        emit-value
        map-options
        class="col chat-model-select"
        :loading="!modelsLoaded"
        :disable="streaming || !modelsLoaded"
      />
    </div>
    <div ref="scrollArea" class="chat-scroll" @click="onMarkdownClick">
      <div class="q-pa-xs">
        <div v-for="(msg, i) in messages" :key="i" class="q-mb-md">
          <div class="text-caption text-grey-7 q-mb-xs chat-meta">
            <span>{{ msg.role === 'user' ? 'あなた' : 'アシスタント' }}</span>
            <span v-if="msg.at" class="chat-meta__time">{{ formatChatTimestamp(msg.at) }}</span>
          </div>
          <div
            v-if="msg.role === 'user'"
            class="chat-bubble chat-bubble--user"
          >
            {{ msg.content }}
          </div>
          <div v-else-if="msg.content || msg.widgets?.length || msg.proposals?.length" class="chat-assistant-block">
            <div v-if="msg.content" class="chat-bubble chat-bubble--assistant">
              <div class="chat-markdown" v-html="renderChatMarkdown(msg.content)" />
            </div>
            <ChatProposalCard
              v-for="prop in msg.proposals ?? []"
              :key="prop.proposal_id"
              :proposal="prop"
              :incident-id="incidentStore.contextIncidentId"
              @accepted="onProposalAccepted"
            />
            <ChatWidgetPrompt
              v-for="widget in msg.widgets ?? []"
              :key="widget.widget_id"
              :widget="widget"
              :disabled="streaming"
            />
            <div
              v-if="msg.durationSec != null || msg.contextUsage"
              class="chat-duration row items-center justify-end no-wrap"
            >
              <span v-if="msg.durationSec != null">
                {{ msg.durationSec }} s<span v-if="msg.model"> · {{ msg.model }}</span>
              </span>
              <span
                v-if="msg.contextUsage && formatMessageContextLabel(msg.contextUsage)"
                class="row items-center no-wrap"
              >
                <span v-if="msg.durationSec != null"> · </span>
                コンテキスト: {{ formatMessageContextLabel(msg.contextUsage) }}
                <ChatContextDonut :usage="msg.contextUsage" class="q-ml-xs" />
              </span>
            </div>
          </div>
          <div
            v-else-if="streaming && i === messages.length - 1"
            class="chat-assistant-block"
          >
            <div class="chat-bubble chat-bubble--assistant text-grey-6 row items-center no-wrap chat-generating">
              <q-spinner size="18px" color="grey-6" class="q-mr-sm" />
              <span>応答を生成中…</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div ref="messageInputAnchor" class="q-mt-sm chat-input-wrap">
      <q-input
        v-model="input"
        type="textarea"
        autogrow
        dense
        outlined
        label="メッセージ"
        class="chat-input"
        :disable="streaming"
        @keydown="onMessageKeydown"
        @dblclick="openTemplateMenu"
      />
    </div>
    <q-menu
      v-if="promptTemplates.length"
      v-model="templateMenuOpen"
      :target="templateMenuTarget"
      anchor="top middle"
      self="bottom middle"
      no-parent-event
      transition-show="scale"
      transition-hide="scale"
    >
      <q-card class="chat-template-card">
        <q-card-section class="q-py-sm text-subtitle2">よく使う質問</q-card-section>
        <q-separator />
        <q-list dense class="chat-template-list">
          <q-item
            v-for="tpl in promptTemplates"
            :key="tpl.id"
            v-close-popup
            clickable
            @click="applyPromptTemplate(tpl.message)"
          >
            <q-item-section>
              <q-item-label>{{ tpl.label }}</q-item-label>
              <q-item-label caption lines="2">{{ tpl.message }}</q-item-label>
            </q-item-section>
          </q-item>
        </q-list>
      </q-card>
    </q-menu>
    <q-btn
      v-if="streaming"
      flat
      color="negative"
      label="中断"
      class="q-mt-sm chat-stop"
      @click="stop"
    />
    <q-btn
      v-else
      color="primary"
      label="送信（Ctrl＋改行）"
      class="q-mt-sm chat-send"
      :disable="!input.trim() || !modelsLoaded || !chatStore.selectedLlm"
      @click="send"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { fetchAiModels, fetchChatPromptTemplates, llmOptionKey, type ChatContextUsage, type ChatPromptTemplate } from '@/api/client'
import aiChatIcon from '@/assets/icons/ai-chat.png'
import { useChatSend } from '@/composables/useChatSend'
import ChatContextDonut from '@/components/chat/ChatContextDonut.vue'
import ChatProposalCard from '@/components/chat/ChatProposalCard.vue'
import ChatWidgetPrompt from '@/components/chat/ChatWidgetPrompt.vue'
import { useChatStore } from '@/stores/chatStore'
import { useIncidentStore } from '@/stores/incidentStore'
import { renderChatMarkdown } from '@/utils/markdown'
import { formatChatTimestamp } from '@/utils/chatTime'

const router = useRouter()
const chatStore = useChatStore()
const incidentStore = useIncidentStore()
const { sendMessage, stopGeneration } = useChatSend()
const { messages, streaming, modelsLoaded } = storeToRefs(chatStore)
const input = ref('')
const scrollArea = ref<HTMLElement | null>(null)
const messageInputAnchor = ref<HTMLElement | null>(null)
const templateMenuTarget = computed(() => messageInputAnchor.value ?? undefined)
const templateMenuOpen = ref(false)
const promptTemplates = ref<ChatPromptTemplate[]>([])

const llmOptions = computed(() =>
  chatStore.modelItems.map((item) => ({
    label: formatLlmLabel(item.provider, item.label),
    value: llmOptionKey(item),
  })),
)

const selectedLlmKey = computed({
  get: () => (chatStore.selectedLlm ? llmOptionKey(chatStore.selectedLlm) : null),
  set: (value: string | null) => {
    if (value) chatStore.setSelectedLlmKey(value)
  },
})

function formatLlmLabel(provider: string, label: string): string {
  const prefix = provider === 'ollama' ? 'Ollama' : 'OpenAI'
  return `${prefix}: ${label}`
}

function formatTokenCount(value: number): string {
  return value.toLocaleString('ja-JP')
}

function formatMessageContextLabel(usage: ChatContextUsage): string {
  const peak = usage.promptTokensPeak ?? usage.promptTokens
  if (peak == null) return ''
  if (usage.contextLimit != null) {
    return `${formatTokenCount(peak)} / ${formatTokenCount(usage.contextLimit)}`
  }
  return `${formatTokenCount(peak)} tokens（上限不明）`
}

onMounted(async () => {
  try {
    const data = await fetchAiModels()
    chatStore.applyModelCatalog(data)
  } catch {
    // 一覧取得失敗時は送信不可のまま
  }
  try {
    promptTemplates.value = await fetchChatPromptTemplates()
  } catch {
    // 定型質問が取得できない場合はポップアップなし
  }
})

async function scrollToBottom() {
  await nextTick()
  const el = scrollArea.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(messages, scrollToBottom, { deep: true })

function onMarkdownClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  const anchor = target.closest('a')
  if (!anchor) return
  const href = anchor.getAttribute('href')
  const match = href?.match(/\/incidents\/(INC-\d{4}-\d{5})/)
  if (!match) return
  event.preventDefault()
  const id = match[1]
  incidentStore.contextIncidentId = id
  router.push({ name: 'detail', params: { id } })
}

function onMessageKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.isComposing) return
  if (!event.ctrlKey) return
  event.preventDefault()
  send()
}

function send() {
  const text = input.value.trim()
  if (!text || streaming.value) return
  if (sendMessage(text)) {
    input.value = ''
    void scrollToBottom()
  }
}

function onProposalAccepted() {
  incidentStore.requestDetailReload()
}

function stop() {
  stopGeneration()
}

function applyPromptTemplate(message: string) {
  input.value = message
  templateMenuOpen.value = false
}

function openTemplateMenu() {
  if (streaming.value || !promptTemplates.value.length) return
  templateMenuOpen.value = true
}
</script>

<style scoped>
.chat-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px;
}

.chat-header-row {
  flex-shrink: 0;
  gap: 8px;
}

.chat-title {
  gap: 6px;
  flex-shrink: 0;
}

.chat-title__icon {
  width: 32px;
  height: auto;
  flex-shrink: 0;
  display: block;
}

.chat-model-select {
  min-width: 0;
  background: #fff;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.chat-input-wrap,
.chat-input,
.chat-send,
.chat-stop {
  flex-shrink: 0;
}

.chat-input {
  background: #fff;
}

.chat-stop {
  border: 1px solid rgba(244, 67, 54, 0.45);
}

.chat-generating {
  gap: 0;
}

.chat-template-card {
  width: min(420px, 90vw);
  max-height: 50vh;
}

.chat-template-list {
  max-height: calc(50vh - 56px);
  overflow: auto;
}

.chat-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.chat-meta__time {
  color: rgba(0, 0, 0, 0.45);
  font-size: 11px;
}

.chat-bubble {
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
}

.chat-bubble--user {
  background: #e3f2fd;
  margin-left: 24px;
}

.chat-bubble--assistant {
  background: #f5f5f5;
}

.chat-assistant-block {
  margin-right: 24px;
}

.chat-duration {
  margin-top: 4px;
  text-align: right;
  font-size: 11px;
  color: rgba(0, 0, 0, 0.45);
  line-height: 1;
  gap: 0;
}

.chat-markdown :deep(p) {
  margin: 0 0 0.5em;
}

.chat-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.chat-markdown :deep(:is(h1, h2, h3, h4, h5, h6)) {
  margin: 0.35em 0 0.2em;
  font-weight: 600;
  line-height: 1.4;
}

.chat-markdown :deep(:is(h1, h2, h3, h4, h5, h6):first-child) {
  margin-top: 0;
}

.chat-markdown :deep(h1) {
  font-size: 1.15em;
}

.chat-markdown :deep(h2) {
  font-size: 1.1em;
}

.chat-markdown :deep(h3) {
  font-size: 1.05em;
}

.chat-markdown :deep(h4),
.chat-markdown :deep(h5),
.chat-markdown :deep(h6) {
  font-size: 1em;
}

.chat-markdown :deep(ul),
.chat-markdown :deep(ol) {
  margin: 0.25em 0 0.5em;
  padding-left: 1.25em;
}

.chat-markdown :deep(li) {
  margin: 0.15em 0;
}

.chat-markdown :deep(code) {
  font-family: Consolas, monospace;
  font-size: 0.9em;
  background: rgba(0, 0, 0, 0.06);
  padding: 0.1em 0.35em;
  border-radius: 3px;
}

.chat-markdown :deep(pre) {
  margin: 0.5em 0;
  padding: 0.5em 0.75em;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-markdown :deep(strong) {
  font-weight: 600;
}

.chat-markdown :deep(a) {
  color: #1976d2;
  text-decoration: underline;
  cursor: pointer;
}

.chat-markdown :deep(table) {
  width: 100%;
  margin: 0.5em 0;
  border-collapse: collapse;
  font-size: 0.9em;
}

.chat-markdown :deep(th),
.chat-markdown :deep(td) {
  border: 1px solid rgba(0, 0, 0, 0.12);
  padding: 0.35em 0.6em;
  text-align: left;
  vertical-align: top;
}

.chat-markdown :deep(th) {
  background: rgba(0, 0, 0, 0.04);
  font-weight: 600;
}
</style>
