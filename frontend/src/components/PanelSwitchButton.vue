<template>
  <q-btn
    flat
    dense
    no-caps
    class="panel-switch gt-sm q-mr-sm"
    :class="{ 'panel-switch--active': active }"
    :aria-label="label"
    :aria-pressed="active"
    @click="active = !active"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 32 32"
      aria-hidden="true"
      class="panel-switch__icon"
    >
      <rect class="panel-switch__frame" x="4" y="8" width="24" height="16" fill="none" stroke-width="2" />
      <rect
        class="panel-switch__marker"
        :x="marker.x"
        :y="marker.y"
        :width="marker.width"
        :height="marker.height"
      />
    </svg>
    <q-tooltip anchor="bottom middle" self="top middle">{{ label }}</q-tooltip>
  </q-btn>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  variant: 'l' | 'r' | 'b'
  label: string
}>()

const active = defineModel<boolean>({ required: true })

const marker = computed(() => {
  switch (props.variant) {
    case 'l':
      return { x: 8, y: 12, width: 4, height: 8 }
    case 'r':
      return { x: 20, y: 12, width: 4, height: 8 }
    case 'b':
      return { x: 8, y: 16, width: 16, height: 4 }
  }
})
</script>

<style scoped>
.panel-switch {
  color: rgba(255, 255, 255, 0.5);
}

.panel-switch--active {
  color: #fff;
}

.panel-switch__frame {
  stroke: currentColor;
}

.panel-switch__marker {
  fill: currentColor;
}
</style>
