<template>
  <q-card flat bordered class="chat-widget q-mt-sm">
    <q-card-section class="q-py-sm">
      <div class="text-subtitle2 q-mb-sm">{{ widget.label }}</div>

      <q-input
        v-if="widget.kind === 'text'"
        v-model="textValue"
        dense
        outlined
        :disable="widget.answered || disabled"
      />

      <q-option-group
        v-else-if="widget.kind === 'radio'"
        v-model="radioValue"
        :options="optionItems"
        type="radio"
        :disable="widget.answered || disabled"
      />

      <q-option-group
        v-else-if="widget.kind === 'checkbox'"
        v-model="checkboxValues"
        :options="optionItems"
        type="checkbox"
        :disable="widget.answered || disabled"
      />

      <q-input
        v-else-if="widget.kind === 'datetime'"
        v-model="datetimeValue"
        dense
        outlined
        type="datetime-local"
        :disable="widget.answered || disabled"
      />

      <div v-if="widget.answered" class="text-caption text-positive q-mt-xs">
        回答済み: {{ widget.answer }}
      </div>

      <div v-else class="q-mt-sm">
        <q-btn
          dense
          color="primary"
          label="送信"
          :disable="disabled || !canSubmit"
          @click="submit"
        />
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChatWidget } from '@/stores/chatStore'
import { buildWidgetAnswerMessage } from '@/composables/useTriage'
import { useChatSend } from '@/composables/useChatSend'
import { useChatStore } from '@/stores/chatStore'

const props = defineProps<{
  widget: ChatWidget
  disabled?: boolean
}>()

const chatStore = useChatStore()
const { sendMessage } = useChatSend()

const textValue = ref('')
const radioValue = ref<string | null>(null)
const checkboxValues = ref<string[]>([])
const datetimeValue = ref('')

const optionItems = computed(() =>
  (props.widget.options ?? []).map((o) => ({ label: o.label, value: o.value })),
)

const canSubmit = computed(() => {
  if (props.widget.kind === 'text') return textValue.value.trim().length > 0
  if (props.widget.kind === 'radio') return !!radioValue.value
  if (props.widget.kind === 'checkbox') return checkboxValues.value.length > 0
  if (props.widget.kind === 'datetime') return !!datetimeValue.value
  return false
})

function submit() {
  let answer = ''
  if (props.widget.kind === 'text') answer = textValue.value.trim()
  else if (props.widget.kind === 'radio') answer = String(radioValue.value ?? '')
  else if (props.widget.kind === 'checkbox') answer = checkboxValues.value.join(', ')
  else if (props.widget.kind === 'datetime') answer = datetimeValue.value

  chatStore.markWidgetAnswered(props.widget.widget_id, answer)
  sendMessage(buildWidgetAnswerMessage(props.widget.widget_id, answer))
}
</script>
