<template>
  <q-list dense bordered separator>
    <q-item clickable v-ripple @click="emit('select', 'thisMonth')" class="quick-filter-item">
      <q-item-section>今月のインシデント</q-item-section>
    </q-item>
    <q-item clickable v-ripple @click="emit('select', 'lastMonth')" class="quick-filter-item">
      <q-item-section>先月のインシデント</q-item-section>
    </q-item>
    <q-item clickable v-ripple @click="emit('select', 'unresolved')" class="quick-filter-item">
      <q-item-section>未解決のインシデント</q-item-section>
    </q-item>
  </q-list>
</template>

<script setup lang="ts">
const emit = defineEmits<{
  select: [filter: 'thisMonth' | 'lastMonth' | 'unresolved']
}>()
</script>

<style lang="css" scoped>
.quick-filter-item {
  background: #fff;
}
</style>
