import { describe, expect, it } from 'vitest'
import { llmOptionKey, parseLlmOptionKey } from '@/api/client'

describe('llmOptionKey', () => {
  it('encodes and decodes provider and model', () => {
    const item = { provider: 'ollama', model: 'qwen3.6:27b' }
    expect(parseLlmOptionKey(llmOptionKey(item))).toEqual(item)
  })
})
