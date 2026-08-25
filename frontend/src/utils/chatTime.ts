/** チャットメッセージ用の ISO タイムスタンプ */
export function chatMessageTimestamp(): string {
  return new Date().toISOString()
}

/** チャット欄表示用（ローカル時刻） */
export function formatChatTimestamp(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

/** 応答時間（ミリ秒を秒に丸め） */
export function elapsedChatSeconds(startedAtMs: number, endedAtMs = performance.now()): number {
  return Math.round((endedAtMs - startedAtMs) / 1000)
}
