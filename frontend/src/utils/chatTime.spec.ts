import { describe, expect, it } from 'vitest'
import { elapsedChatSeconds, formatChatTimestamp } from '@/utils/chatTime'

describe('formatChatTimestamp', () => {
  it('formats ISO string for display', () => {
    const formatted = formatChatTimestamp('2026-06-24T08:30:45.123Z')
    expect(formatted).toMatch(/2026/)
    expect(formatted).toMatch(/30/)
  })
})

describe('elapsedChatSeconds', () => {
  it('rounds milliseconds to seconds', () => {
    expect(elapsedChatSeconds(1000, 1499)).toBe(0)
    expect(elapsedChatSeconds(1000, 1500)).toBe(1)
    expect(elapsedChatSeconds(0, 3200)).toBe(3)
  })
})
