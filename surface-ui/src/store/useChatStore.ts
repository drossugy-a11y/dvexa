import { create } from 'zustand'
import {
  submitChat,
  getChatHistory,
  connectChatStream,
  type ChatMessage,
  type TimelineEvent,
  type WsStatus,
} from '../api/chat'

export type RuntimeState = 'idle' | 'submitting' | 'streaming' | 'completed' | 'error'

interface ChatState {
  messages: ChatMessage[]
  events: TimelineEvent[]
  activeTaskId: string | null
  runtimeState: RuntimeState
  error: string | null
  ws: WebSocket | null
  wsStatus: WsStatus
  runtimeDrawerOpen: boolean
  sidebarVisible: boolean

  sendMessage: (message: string) => Promise<void>
  fetchHistory: () => Promise<void>
  clearError: () => void
  resetState: () => void
  setRuntimeDrawerOpen: (open: boolean) => void
  toggleSidebar: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  events: [],
  activeTaskId: null,
  runtimeState: 'idle',
  error: null,
  ws: null,
  wsStatus: 'idle',
  runtimeDrawerOpen: false,
  sidebarVisible: true,

  sendMessage: async (message: string) => {
    const state = get()
    if (state.runtimeState !== 'idle') return

    set({
      runtimeState: 'submitting',
      error: null,
      events: [],
      wsStatus: 'connected',
    })

    const res = await submitChat(message)
    if (!res.success || !res.data) {
      set({
        runtimeState: 'error',
        error: res.error ?? 'Submit failed',
        wsStatus: 'disconnected',
      })
      return
    }

    const { task_id } = res.data
    set({ activeTaskId: task_id, runtimeState: 'streaming' })

    // Connect WebSocket with full lifecycle
    const ws = connectChatStream(task_id, {
      onEvent: (event) => {
        const s = get()

        // stream_completed → unlock
        if (event.event_type === 'stream_completed') {
          set({ runtimeState: 'completed', wsStatus: 'idle' })
          // Auto-reset back to idle after a short delay
          setTimeout(() => {
            set({ runtimeState: 'idle' })
          }, 500)
          return
        }

        if (event.event_type === 'stream_error' || event.event_type === 'error') {
          set({ runtimeState: 'error', error: event.content ?? 'Stream error' })
          return
        }

        // Append to events
        set({ events: [...s.events, event] })
      },
      onStatusChange: (status) => {
        set({ wsStatus: status })
        if (status === 'disconnected') {
          const s = get()
          if (s.runtimeState === 'streaming') {
            set({ runtimeState: 'error', error: 'Connection lost' })
          }
        }
      },
      onError: (err) => {
        set({ error: err })
      },
    })

    set({ ws })

    // Safety timeout: force unlock after 120s
    setTimeout(() => {
      const s = get()
      if (s.runtimeState === 'streaming' || s.runtimeState === 'submitting') {
        set({ runtimeState: 'error', error: 'Response timeout' })
        // Fetch history one last time to get any partial result
        get().fetchHistory()
      }
    }, 120_000)
  },

  fetchHistory: async () => {
    const res = await getChatHistory()
    if (res.success && res.data) {
      const current = get()
      // Dedup by task_id + role to avoid duplication
      const existing = new Set(
        current.messages.map((m) => `${m.task_id}:${m.role}:${m.content}`),
      )
      const newMessages = res.data.filter(
        (m) => !existing.has(`${m.task_id}:${m.role}:${m.content}`),
      )
      if (newMessages.length > 0) {
        set({ messages: [...current.messages, ...newMessages] })
      }
    }
  },

  clearError: () => set({ error: null }),

  resetState: () => {
    const ws = get().ws
    if (ws) {
      ws.close()
    }
    set({
      runtimeState: 'idle',
      error: null,
      activeTaskId: null,
      ws: null,
      wsStatus: 'idle',
    })
  },

  setRuntimeDrawerOpen: (open) => set({ runtimeDrawerOpen: open }),

  toggleSidebar: () => set((s) => ({ sidebarVisible: !s.sidebarVisible })),
}))
