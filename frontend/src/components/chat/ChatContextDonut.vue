<template>
  <svg
    v-if="ratio != null"
    class="chat-context-donut"
    viewBox="0 0 16 16"
    width="12"
    height="12"
    aria-hidden="true"
  >
    <circle
      cx="8"
      cy="8"
      r="6"
      fill="none"
      stroke="rgba(0, 0, 0, 0.12)"
      stroke-width="3"
    />
    <circle
      cx="8"
      cy="8"
      r="6"
      fill="none"
      :stroke="color"
      stroke-width="3"
      stroke-linecap="round"
      :stroke-dasharray="circumference"
      :stroke-dashoffset="dashOffset"
      transform="rotate(-90 8 8)"
    />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatContextUsage } from '@/api/client'

const props = defineProps<{
  usage: ChatContextUsage
}>()

const RADIUS = 6
const circumference = 2 * Math.PI * RADIUS

const ratio = computed(() => {
  const usage = props.usage
  if (usage.usageRatio != null) return Math.min(1, Math.max(0, usage.usageRatio))
  const peak = usage.promptTokensPeak ?? usage.promptTokens
  if (peak != null && usage.contextLimit != null) {
    return Math.min(1, Math.max(0, peak / usage.contextLimit))
  }
  return null
})

const dashOffset = computed(() => {
  const r = ratio.value
  if (r == null) return circumference
  return circumference * (1 - r)
})

const color = computed(() => {
  const r = ratio.value
  if (r == null) return '#1976d2'
  if (r >= 0.9) return '#c10015'
  if (r >= 0.7) return '#f2c037'
  return '#1976d2'
})
</script>

<style scoped>
.chat-context-donut {
  display: inline-block;
  vertical-align: -1px;
  flex-shrink: 0;
}
</style>
