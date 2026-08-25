import { onUnmounted, ref, type Ref } from 'vue'

const MIN_WIDTH_PX = 280

export function chatPanelMaxWidthPx(): number {
  return Math.round(window.innerWidth * 0.75)
}

export function chatPanelDefaultWidthPx(): number {
  return Math.round(window.innerWidth * 0.4)
}

export function clampChatPanelWidth(px: number): number {
  return Math.min(chatPanelMaxWidthPx(), Math.max(MIN_WIDTH_PX, Math.round(px)))
}

export function useChatPanelResize(widthPx: Ref<number>) {
  const resizing = ref(false)
  let startX = 0
  let startWidth = 0

  function onMouseMove(event: MouseEvent) {
    if (!resizing.value) return
    const delta = startX - event.clientX
    widthPx.value = clampChatPanelWidth(startWidth + delta)
  }

  function onMouseUp() {
    if (!resizing.value) return
    resizing.value = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  function startResize(event: MouseEvent) {
    event.preventDefault()
    resizing.value = true
    startX = event.clientX
    startWidth = widthPx.value
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  onUnmounted(onMouseUp)

  return { resizing, startResize }
}
