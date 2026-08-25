import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { buildSimilarIncidentsMessage, useChatSend } from '@/composables/useChatSend'
import { useChatStore } from '@/stores/chatStore'
import { useIncidentStore } from '@/stores/incidentStore'

vi.mock('@/api/client', () => ({
  streamChat: vi.fn(),
}))

import { streamChat } from '@/api/client'

describe('buildSimilarIncidentsMessage', () => {
  it('builds similar-incidents prompt with incident ID', () => {
    expect(buildSimilarIncidentsMessage('INC-2026-00039')).toBe(
      'INC-2026-00039と類似したインシデントを最大10件リストアップしてください。',
    )
  })
})

describe('useChatSend', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(streamChat).mockReset()
  })

  it('adds user message and starts streaming', () => {
    const chatStore = useChatStore()
    const incidentStore = useIncidentStore()
    incidentStore.contextIncidentId = 'INC-2026-00039'
    chatStore.applyModelCatalog({
      default: { provider: 'ollama', model: 'qwen3.6:27b' },
      items: [{ provider: 'ollama', model: 'qwen3.6:27b', label: 'qwen3.6:27b' }],
      sources: [],
    })
    const { sendMessage } = useChatSend()

    expect(sendMessage('hello')).toBe(true)
    expect(chatStore.messages).toHaveLength(2)
    expect(chatStore.messages[0]).toMatchObject({ role: 'user', content: 'hello' })
    expect(chatStore.streaming).toBe(true)
    expect(streamChat).toHaveBeenCalledWith(
      [{ role: 'user', content: 'hello' }],
      {
        contextIncidentId: 'INC-2026-00039',
        llmProvider: 'ollama',
        model: 'qwen3.6:27b',
      },
      expect.objectContaining({
        onToken: expect.any(Function),
        onDone: expect.any(Function),
        onError: expect.any(Function),
      }),
    )
  })

  it('stopGeneration aborts active stream and marks interruption', () => {
    let onAbort: (() => void) | undefined
    const abortFn = vi.fn()
    vi.mocked(streamChat).mockImplementation((_history, _opts, callbacks) => {
      onAbort = callbacks.onAbort
      return abortFn
    })
    const chatStore = useChatStore()
    chatStore.applyModelCatalog({
      default: { provider: 'ollama', model: 'qwen3.6:27b' },
      items: [{ provider: 'ollama', model: 'qwen3.6:27b', label: 'qwen3.6:27b' }],
      sources: [],
    })
    const { sendMessage, stopGeneration } = useChatSend()

    sendMessage('hello')
    chatStore.appendAssistantToken('途中')
    expect(stopGeneration()).toBe(true)
    expect(abortFn).toHaveBeenCalled()
    onAbort?.()

    expect(chatStore.streaming).toBe(false)
    expect(chatStore.messages.at(-1)).toMatchObject({
      role: 'assistant',
      content: expect.stringMatching(/途中.*（\d+秒で中断）$/),
    })
  })

  it('stopGeneration returns false when not streaming', () => {
    const { stopGeneration } = useChatSend()
    expect(stopGeneration()).toBe(false)
  })

  it('returns false while streaming', () => {
    const chatStore = useChatStore()
    chatStore.streaming = true
    const { sendMessage } = useChatSend()

    expect(sendMessage('hello')).toBe(false)
    expect(streamChat).not.toHaveBeenCalled()
  })
})
