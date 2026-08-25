import { describe, expect, it } from 'vitest'
import { parseSseLines } from '@/api/client'

describe('parseSseLines', () => {
  it('parses single-line SSE events', () => {
    const input = 'data: {"type":"token","content":"a"}\ndata: {"type":"token","content":"b"}\n'
    const { events, rest } = parseSseLines(input)
    expect(events).toHaveLength(2)
    expect(events[0]).toEqual({ type: 'token', content: 'a' })
    expect(events[1]).toEqual({ type: 'token', content: 'b' })
    expect(rest).toBe('')
  })

  it('parses proposal and widget SSE events', () => {
    const input =
      'data: {"type":"proposal","proposal_id":"p1","field":"severity"}\n' +
      'data: {"type":"widget","widget_id":"w1","kind":"text","label":"入力"}\n'
    const { events } = parseSseLines(input)
    expect(events[0]?.type).toBe('proposal')
    expect(events[1]?.type).toBe('widget')
  })

  it('keeps incomplete trailing line in buffer', () => {
    const input = 'data: {"type":"token","content":"ok"}\ndata: {"type":"to'
    const { events, rest } = parseSseLines(input)
    expect(events).toHaveLength(1)
    expect(rest).toBe('data: {"type":"to')
  })
})
