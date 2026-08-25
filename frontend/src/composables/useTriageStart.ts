import { onMounted, watch, type MaybeRefOrGetter, toValue } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatSend } from '@/composables/useChatSend'
import { buildTriageStartMessage } from '@/composables/useTriage'
import { useIncidentStore } from '@/stores/incidentStore'
import { useUiStore } from '@/stores/uiStore'

/** 詳細画面で ?triage=1 のときチャットを開きトリアージを自動開始する */
export function useTriageStart(incidentId: MaybeRefOrGetter<string>) {
  const route = useRoute()
  const router = useRouter()
  const uiStore = useUiStore()
  const incidentStore = useIncidentStore()
  const { sendMessage } = useChatSend()

  function maybeStartTriage() {
    if (route.query.triage !== '1') return
    const id = toValue(incidentId)
    incidentStore.contextIncidentId = id
    uiStore.openChatPanel()
    const started = sendMessage(buildTriageStartMessage())
    if (started) {
      const q = { ...route.query }
      delete q.triage
      router.replace({ query: q })
    }
  }

  onMounted(() => {
    maybeStartTriage()
  })

  watch(
    () => route.query.triage,
    () => maybeStartTriage(),
  )
}
