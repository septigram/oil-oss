/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from 'vitest'
import {
  chatPanelDefaultWidthPx,
  chatPanelMaxWidthPx,
  clampChatPanelWidth,
} from '@/composables/useChatPanelResize'

describe('useChatPanelResize helpers', () => {
  it('default width is 40vw', () => {
    vi.stubGlobal('innerWidth', 1000)
    expect(chatPanelDefaultWidthPx()).toBe(400)
  })

  it('clamps width between min and 75vw', () => {
    vi.stubGlobal('innerWidth', 1000)
    expect(clampChatPanelWidth(100)).toBe(280)
    expect(clampChatPanelWidth(800)).toBe(750)
    expect(clampChatPanelWidth(500)).toBe(500)
  })

  it('max width is 75vw', () => {
    vi.stubGlobal('innerWidth', 1200)
    expect(chatPanelMaxWidthPx()).toBe(900)
  })
})
