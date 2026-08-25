import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatPanelDefaultWidthPx, clampChatPanelWidth } from '@/composables/useChatPanelResize'

export const useUiStore = defineStore('ui', () => {
  const showQuickFilter = ref(true)
  const showChat = ref(true)
  const showLogPanel = ref(false)
  const serverReachable = ref(true)
  const chatPanelWidthPx = ref(chatPanelDefaultWidthPx())

  function setChatPanelWidth(px: number) {
    chatPanelWidthPx.value = clampChatPanelWidth(px)
  }

  function resetChatPanelWidth() {
    chatPanelWidthPx.value = chatPanelDefaultWidthPx()
  }

  const chatPanelOpenNonce = ref(0)

  function openChatPanel() {
    showChat.value = true
    chatPanelOpenNonce.value++
  }

  function setServerReachable(reachable: boolean) {
    serverReachable.value = reachable
  }

  return {
    showQuickFilter,
    showChat,
    showLogPanel,
    serverReachable,
    chatPanelWidthPx,
    chatPanelOpenNonce,
    setChatPanelWidth,
    resetChatPanelWidth,
    openChatPanel,
    setServerReachable,
  }
})
