/** 重要度 Chip の Quasar color 名 */
export function severityChipColor(severity: string | undefined | null): string {
  switch (severity) {
    case 'CRITICAL':
      return 'purple'
    case 'HIGH':
      return 'negative'
    case 'MEDIUM':
      return 'orange'
    case 'LOW':
      return 'positive'
    default:
      return 'grey'
  }
}
