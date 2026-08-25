<template>
  <q-chip
    v-if="severity"
    dense
    class="severity-chip"
    :color="severityChipColor(severity)"
    text-color="white"
    :label="severity"
  />
</template>

<script setup lang="ts">
import { severityChipColor } from '@/utils/severityChip'

defineProps<{
  severity: string | undefined | null
}>()
</script>

<style scoped>
.severity-chip {
  font-size: 11px;
}

.severity-chip :deep(.q-chip__content) {
  line-height: 1.2;
}
</style>
