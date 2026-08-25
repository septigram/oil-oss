import { streamChat } from '@/api/client'
import { useChatStore } from '@/stores/chatStore'
import { useIncidentStore } from '@/stores/incidentStore'
import { elapsedChatSeconds } from '@/utils/chatTime'

export function buildSimilarIncidentsMessage(incidentId: string): string {
  return `${incidentId}と類似したインシデントを最大10件リストアップしてください。`
}

/** 進行中のチャットストリーム（同時に 1 件のみ） */
let activeStreamAbort: (() => void) | null = null

function clearActiveStreamAbort() {
  activeStreamAbort = null
}

export function useChatSend() {
  const chatStore = useChatStore()
  const incidentStore = useIncidentStore()

  function sendMessage(text: string): boolean {
    const trimmed = text.trim()
    if (!trimmed || chatStore.streaming || !chatStore.selectedLlm) return false

    const { provider, model } = chatStore.selectedLlm

    chatStore.addUserMessage(trimmed)
    chatStore.streaming = true
    chatStore.startAssistantMessage(model)
    const startedAt = performance.now()
    const history = chatStore.buildApiHistory()

    const endStream = () => {
      chatStore.streaming = false
      clearActiveStreamAbort()
    }

    activeStreamAbort = streamChat(
      history,
      {
        contextIncidentId: incidentStore.contextIncidentId,
        llmProvider: provider,
        model,
      },
      {
        onToken: (token) => chatStore.appendAssistantToken(token),
        onWidget: (widget) => chatStore.appendAssistantWidget(widget),
        onProposal: (proposal) => chatStore.appendAssistantProposal(proposal),
        onUsage: (usage) => chatStore.setContextUsage(usage),
        onDone: () => {
          endStream()
          chatStore.finalizeAssistantOrError('応答を生成できませんでした。もう一度お試しください。')
          chatStore.setAssistantDuration(elapsedChatSeconds(startedAt))
        },
        onError: (message) => {
          endStream()
          chatStore.finalizeAssistantOrError(`エラー: ${message}`)
          chatStore.setAssistantDuration(elapsedChatSeconds(startedAt))
        },
        onAbort: () => {
          endStream()
          chatStore.markAssistantInterrupted(elapsedChatSeconds(startedAt))
        },
      },
    )
    return true
  }

  function stopGeneration(): boolean {
    if (!chatStore.streaming || !activeStreamAbort) return false
    activeStreamAbort()
    return true
  }

  return { sendMessage, stopGeneration }
}
