type ValidationDetail = {
  loc?: unknown[]
  msg?: string
}

const FIELD_LABELS: Record<string, string> = {
  summary: '概要',
  detail: '詳細',
  started_at: '開始日時',
  ended_at: '終了日時',
  response_type: '対応種別',
  title: 'タイトル',
  description: '説明',
  occurred_at: '発生日時',
}

function fieldLabel(loc: unknown[] | undefined): string {
  if (!loc?.length) return ''
  const key = loc[loc.length - 1]
  return typeof key === 'string' ? (FIELD_LABELS[key] ?? key) : ''
}

function formatValidationDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const lines = detail
      .filter((item): item is ValidationDetail => !!item && typeof item === 'object')
      .map((item) => {
        const label = fieldLabel(item.loc)
        const msg = item.msg ?? '不正な値です'
        return label ? `${label}: ${msg}` : msg
      })
    return lines.length ? lines.join(' / ') : fallback
  }
  if (detail && typeof detail === 'object' && 'msg' in detail) {
    return String((detail as ValidationDetail).msg ?? fallback)
  }
  return fallback
}

/** axios エラーからユーザー向けメッセージを取り出す。FastAPI の validation error 配列にも対応。 */
export function formatApiError(err: unknown, fallback = '操作に失敗しました'): string {
  if (!err || typeof err !== 'object' || !('response' in err)) {
    return fallback
  }
  const data = (err as { response?: { data?: { detail?: unknown; message?: string } } }).response?.data
  if (data && typeof data.message === 'string' && data.message) {
    return data.message
  }
  if (!data || !('detail' in data)) return fallback
  return formatValidationDetail(data.detail, fallback)
}
