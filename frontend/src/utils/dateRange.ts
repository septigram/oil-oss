/** ローカル暦日を YYYY-MM-DD で返す（toISOString は JST で前日になるため使わない） */
export function formatLocalDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 基準日文字列と月オフセットから一覧フィルタ用の日付範囲を算出する */
export function monthRange(refDate: string, offset: number): { from: string; to: string } {
  const [year, month, day] = refDate.split('-').map(Number)
  const ref = new Date(year, month - 1, day)
  const targetMonth = ref.getMonth() + offset
  const targetYear = ref.getFullYear() + Math.floor(targetMonth / 12)
  const normalizedMonth = ((targetMonth % 12) + 12) % 12
  const start = new Date(targetYear, normalizedMonth, 1)
  const end =
    offset === 0
      ? ref
      : new Date(targetYear, normalizedMonth + 1, 0)
  return { from: formatLocalDate(start), to: formatLocalDate(end) }
}
