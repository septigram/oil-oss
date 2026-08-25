<template>
  <div class="log-panel column">
    <div class="text-subtitle2 q-px-sm q-pt-sm">サーバーログ</div>
    <div ref="scrollEl" class="log-scroll col q-pa-xs">
      <div
        v-for="entry in entries"
        :key="entry.seq"
        class="log-line q-mb-xs cursor-pointer"
        @dblclick="toggleExpand(entry.seq)"
      >
        <span class="log-ts text-grey-7">{{ entry.ts }}</span>
        <span class="log-event text-weight-medium q-ml-sm">{{ entry.event }}</span>
        <template v-if="!expanded.has(entry.seq)">
          <span class="log-summary q-ml-sm">{{ formatLogSummary(entry) }}</span>
        </template>
        <pre v-else class="log-json q-ma-none q-mt-xs">{{ formatJson(entry, true) }}</pre>
      </div>
      <div v-if="entries.length === 0" class="text-grey-6 q-pa-sm">ログはまだありません</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { fetchRecentLogs, type LogEntry } from '@/api/client'
import { useUiStore } from '@/stores/uiStore'

const POLL_INTERVAL_MS = 2500
const MAX_LINES = 1000

const entries = ref<LogEntry[]>([])
const expanded = ref(new Set<number>())
const cursor = ref(0)
const scrollEl = ref<HTMLElement | null>(null)
let timer: ReturnType<typeof setInterval> | null = null
const uiStore = useUiStore()

function formatJson(entry: LogEntry, pretty: boolean): string {
  return pretty ? JSON.stringify(entry, null, 2) : JSON.stringify(entry)
}

function formatLogSummary(entry: LogEntry): string {
  if (entry.event === 'mcp_tool') {
    const toolName = String(entry.tool_name ?? '')
    const params = JSON.stringify(entry.parameters ?? {})
    const preview = String(entry.response_preview ?? '')
    const chars = entry.response_chars ?? 0
    return `tool=${toolName} params=${params} response=${preview} (${chars}文字)`
  }
  return formatJson(entry, false)
}

function toggleExpand(seq: number) {
  const next = new Set(expanded.value)
  if (next.has(seq)) next.delete(seq)
  else next.add(seq)
  expanded.value = next
}

function appendItems(items: LogEntry[]) {
  if (items.length === 0) return
  const merged = [...entries.value, ...items]
  if (merged.length > MAX_LINES) {
    const removed = merged.length - MAX_LINES
    const kept = merged.slice(removed)
    const removedSeqs = new Set(merged.slice(0, removed).map((e) => e.seq))
    expanded.value = new Set([...expanded.value].filter((s) => !removedSeqs.has(s)))
    entries.value = kept
  } else {
    entries.value = merged
  }
  scrollToBottom()
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    const el = scrollEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function poll() {
  try {
    const data = await fetchRecentLogs(cursor.value)
    uiStore.setServerReachable(true)
    cursor.value = data.next_cursor
    appendItems(data.items)
  } catch {
    uiStore.setServerReachable(false)
  }
}

onMounted(() => {
  void poll()
  timer = setInterval(() => void poll(), POLL_INTERVAL_MS)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.log-panel {
  height: 100%;
  min-height: 0;
}

.log-scroll {
  overflow: auto;
  min-height: 0;
  font-family: Consolas, monospace;
  font-size: 12px;
}

.log-line {
  padding: 2px 4px;
  border-radius: 3px;
}

.log-line:hover {
  background: rgba(0, 0, 0, 0.04);
}

.log-ts {
  font-size: 11px;
}

.log-json {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.04);
  padding: 4px 8px;
  border-radius: 3px;
}
</style>
