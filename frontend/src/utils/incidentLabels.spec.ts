import { describe, expect, it } from 'vitest'
import { statusDisplayLabel } from '@/utils/incidentLabels'

describe('statusDisplayLabel', () => {
  it('maps DB values to Japanese labels', () => {
    expect(statusDisplayLabel('OPEN')).toBe('未着手')
    expect(statusDisplayLabel('IN_PROGRESS')).toBe('対応中')
    expect(statusDisplayLabel('RESOLVED')).toBe('解決済み')
  })

  it('falls back to raw value when unknown', () => {
    expect(statusDisplayLabel('UNKNOWN')).toBe('UNKNOWN')
    expect(statusDisplayLabel(null)).toBe('')
  })
})
