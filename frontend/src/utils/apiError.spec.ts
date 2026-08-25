import { describe, expect, it } from 'vitest'
import { formatApiError } from './apiError'

describe('formatApiError', () => {
  it('文字列 detail をそのまま返す', () => {
    const err = { response: { data: { detail: 'インシデントが見つかりません' } } }
    expect(formatApiError(err, '失敗')).toBe('インシデントが見つかりません')
  })

  it('FastAPI validation error 配列を整形する', () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ['body', 'started_at'], msg: 'Field required', type: 'missing' },
            { loc: ['body', 'summary'], msg: 'String should have at least 1 character', type: 'string_too_short' },
          ],
        },
      },
    }
    expect(formatApiError(err, '失敗')).toBe(
      '開始日時: Field required / 概要: String should have at least 1 character',
    )
  })

  it('response が無い場合は fallback', () => {
    expect(formatApiError(new Error('network'), '登録に失敗しました')).toBe('登録に失敗しました')
  })
})
