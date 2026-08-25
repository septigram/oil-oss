import { useQuasar } from 'quasar'
import { isOptimisticLockConflict, type OptimisticLockConflictBody } from '@/api/client'

export type ConflictChoice = 'reload' | 'cancel'

export function conflictMessage(err: unknown): string {
  if (!isOptimisticLockConflict(err)) {
    return '他のユーザによって更新されました。最新の内容を読み込んでください。'
  }
  const data = err.response?.data as OptimisticLockConflictBody
  return data.message || '他のユーザによって更新されました。最新の内容を読み込んでください。'
}

export function useOptimisticLockConflict() {
  const $q = useQuasar()

  function showConflictDialog(message: string): Promise<ConflictChoice> {
    return new Promise((resolve) => {
      $q.dialog({
        title: '更新の競合',
        message,
        ok: { label: '最新を読み込む', color: 'primary', flat: false },
        cancel: { label: 'キャンセル', flat: true },
        persistent: true,
      })
        .onOk(() => resolve('reload'))
        .onCancel(() => resolve('cancel'))
        .onDismiss(() => resolve('cancel'))
    })
  }

  async function handleConflict(
    err: unknown,
    onReload: () => void | Promise<void>,
  ): Promise<boolean> {
    if (!isOptimisticLockConflict(err)) return false
    const choice = await showConflictDialog(conflictMessage(err))
    if (choice === 'reload') await onReload()
    return true
  }

  return { showConflictDialog, handleConflict, isOptimisticLockConflict, conflictMessage }
}
