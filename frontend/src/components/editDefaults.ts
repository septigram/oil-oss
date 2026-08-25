import { useAuthStore } from '@/stores/authStore'

/** datetime-local 入力用の現在日時（ブラウザローカル） */
export function nowLocalDateTime(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function getSettings() {
  const auth = useAuthStore()
  return {
    operatorId: auth.employeeId || 'EMP-00001',
    departmentId: auth.departmentId || 'DEPT-OPS',
    occurredAtLocal: nowLocalDateTime(),
  }
}
