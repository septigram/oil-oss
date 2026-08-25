import { describe, expect, it } from 'vitest'
import { formatLocalDate, monthRange } from '@/utils/dateRange'

describe('dateRange', () => {
  it('formats local calendar date without UTC shift', () => {
    const d = new Date(2020, 3, 1)
    expect(formatLocalDate(d)).toBe('2020-04-01')
  })

  it('returns this month through reference date', () => {
    expect(monthRange('2020-05-31', 0)).toEqual({ from: '2020-05-01', to: '2020-05-31' })
  })

  it('returns previous calendar month', () => {
    expect(monthRange('2020-05-31', -1)).toEqual({ from: '2020-04-01', to: '2020-04-30' })
  })
})
