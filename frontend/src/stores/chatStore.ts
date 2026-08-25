import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  llmOptionKey,
  parseLlmOptionKey,
  type AiLlmModel,
  type AiModelsResponse,
  type ChatContextUsage,
  type ChatProposalEvent,
  type ChatWidgetEvent,
} from '@/api/client'
import { chatMessageTimestamp } from '@/utils/chatTime'

export interface ChatWidget extends ChatWidgetEvent {
  answered?: boolean
  answer?: string
}

export interface ChatProposal extends ChatProposalEvent {
  status?: 'pending' | 'accepted' | 'rejected'
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  at: string
  durationSec?: number
  model?: string
  contextUsage?: ChatContextUsage
  widgets?: ChatWidget[]
  proposals?: ChatProposal[]
}

export interface SelectedLlm {
  provider: string
  model: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const modelItems = ref<AiLlmModel[]>([])
  const selectedLlm = ref<SelectedLlm | null>(null)
  const modelsLoaded = ref(false)

  function addUserMessage(content: string) {
    messages.value.push({ role: 'user', content, at: chatMessageTimestamp() })
  }

  function startAssistantMessage(model: string) {
    messages.value.push({ role: 'assistant', content: '', at: chatMessageTimestamp(), model })
  }

  function appendAssistantToken(token: string) {
    const idx = messages.value.length - 1
    const last = messages.value[idx]
    if (last?.role === 'assistant') {
      messages.value[idx] = {
        ...last,
        content: last.content + token,
        widgets: last.widgets,
        proposals: last.proposals,
      }
    }
  }

  function appendAssistantWidget(widget: ChatWidgetEvent) {
    const idx = messages.value.length - 1
    const last = messages.value[idx]
    if (last?.role !== 'assistant') return
    const widgets = [...(last.widgets ?? []), { ...widget }]
    messages.value[idx] = { ...last, widgets }
  }

  function appendAssistantProposal(proposal: ChatProposalEvent) {
    const idx = messages.value.length - 1
    const last = messages.value[idx]
    if (last?.role !== 'assistant') return
    const proposals = [...(last.proposals ?? []), { ...proposal, status: 'pending' as const }]
    messages.value[idx] = { ...last, proposals }
  }

  function updateProposalStatus(proposalId: string, status: 'accepted' | 'rejected') {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]
      if (msg.role !== 'assistant' || !msg.proposals?.length) continue
      const proposals = msg.proposals.map((p) =>
        p.proposal_id === proposalId ? { ...p, status } : p,
      )
      if (proposals.some((p, j) => p.status !== msg.proposals![j].status)) {
        messages.value[i] = { ...msg, proposals }
        return
      }
    }
  }

  function markWidgetAnswered(widgetId: string, answer: string) {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]
      if (msg.role !== 'assistant' || !msg.widgets?.length) continue
      const widgets = msg.widgets.map((w) =>
        w.widget_id === widgetId ? { ...w, answered: true, answer } : w,
      )
      if (widgets.some((w, j) => w.answered !== msg.widgets![j].answered)) {
        messages.value[i] = { ...msg, widgets }
        return
      }
    }
  }

  /** API 送信用。末尾の空 assistant プレースホルダを除く */
  function buildApiHistory(): Array<{ role: 'user' | 'assistant'; content: string }> {
    return messages.value
      .filter((m) => m.role !== 'assistant' || m.content.trim())
      .map((m) => ({ role: m.role, content: m.content }))
  }

  function finalizeAssistantOrError(fallback: string) {
    const idx = messages.value.length - 1
    const last = messages.value[idx]
    if (last?.role === 'assistant' && !last.content.trim()) {
      messages.value[idx] = {
        ...last,
        content: fallback,
      }
    }
  }

  function setAssistantDuration(durationSec: number) {
    const idx = messages.value.length - 1
    const last = messages.value[idx]
    if (last?.role === 'assistant') {
      messages.value[idx] = { ...last, durationSec }
    }
  }

  function markAssistantInterrupted(durationSec: number) {
    const idx = messages.value.length - 1
    const last = messages.value[idx]
    if (last?.role !== 'assistant') return
    const suffix = `（${durationSec}秒で中断）`
    const content = last.content.trim() ? `${last.content}${suffix}` : suffix
    messages.value[idx] = { ...last, content, durationSec }
  }

  function applyModelCatalog(data: AiModelsResponse) {
    modelItems.value = data.items
    modelsLoaded.value = true

    if (!selectedLlm.value) {
      selectedLlm.value = { ...data.default }
      return
    }

    const currentKey = llmOptionKey(selectedLlm.value)
    const validKeys = new Set(data.items.map((item) => llmOptionKey(item)))
    validKeys.add(llmOptionKey(data.default))
    if (!validKeys.has(currentKey)) {
      selectedLlm.value = { ...data.default }
    }
  }

  function setSelectedLlmKey(key: string) {
    selectedLlm.value = parseLlmOptionKey(key)
  }

  function setContextUsage(usage: ChatContextUsage) {
    const idx = messages.value.length - 1
    const last = messages.value[idx]
    if (last?.role === 'assistant') {
      messages.value[idx] = { ...last, contextUsage: usage }
    }
  }

  function clear() {
    messages.value = []
  }

  return {
    messages,
    streaming,
    modelItems,
    selectedLlm,
    modelsLoaded,
    addUserMessage,
    startAssistantMessage,
    appendAssistantToken,
    appendAssistantWidget,
    appendAssistantProposal,
    updateProposalStatus,
    markWidgetAnswered,
    buildApiHistory,
    finalizeAssistantOrError,
    setAssistantDuration,
    markAssistantInterrupted,
    applyModelCatalog,
    setSelectedLlmKey,
    setContextUsage,
    clear,
  }
})
