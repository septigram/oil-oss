/** status の DB値 → 画面表示（backend STATUS_SPECS と同一） */
const STATUS_DISPLAY: Record<string, string> = {
  OPEN: '未着手',
  IN_PROGRESS: '対応中',
  RESOLVED: '解決済み',
}

export function statusDisplayLabel(status: string | undefined | null): string {
  if (!status) return ''
  return STATUS_DISPLAY[status] ?? status
}
