import { describe, expect, it } from 'vitest'
import { severityChipColor } from '@/utils/severityChip'

describe('severityChipColor', () => {
  it('maps severity levels to chip colors', () => {
    expect(severityChipColor('CRITICAL')).toBe('purple')
    expect(severityChipColor('HIGH')).toBe('negative')
    expect(severityChipColor('MEDIUM')).toBe('orange')
    expect(severityChipColor('LOW')).toBe('positive')
  })

  it('falls back to grey for unknown values', () => {
    expect(severityChipColor('UNKNOWN')).toBe('grey')
    expect(severityChipColor(null)).toBe('grey')
  })
})
