import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useChatStore } from '@/stores/chatStore'

describe('chatStore markAssistantInterrupted', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('appends interruption suffix to partial response', () => {
    const store = useChatStore()
    store.startAssistantMessage('qwen3.6:27b')
    store.appendAssistantToken('回答の一部')
    store.markAssistantInterrupted(3)
    expect(store.messages[0].content).toBe('回答の一部（3秒で中断）')
    expect(store.messages[0].durationSec).toBe(3)
    expect(store.messages[0].model).toBe('qwen3.6:27b')
  })

  it('shows only suffix when response is empty', () => {
    const store = useChatStore()
    store.startAssistantMessage('qwen3.6:27b')
    store.markAssistantInterrupted(1)
    expect(store.messages[0].content).toBe('（1秒で中断）')
  })

  it('stores context usage on the latest assistant message from SSE usage event', () => {
    const store = useChatStore()
    store.startAssistantMessage('qwen3.6:27b')
    store.setContextUsage({
      promptTokens: 1200,
      promptTokensPeak: 1500,
      outputTokens: 80,
      outputTokensTotal: 200,
      contextLimit: 8192,
      remainingEstimate: 6692,
      usageRatio: 1500 / 8192,
      llmCalls: 2,
    })
    expect(store.messages[0].contextUsage?.promptTokensPeak).toBe(1500)
    expect(store.messages[0].contextUsage?.remainingEstimate).toBe(6692)
    expect(store.messages[0].contextUsage?.llmCalls).toBe(2)
  })
})
