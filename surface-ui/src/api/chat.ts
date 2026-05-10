import type { ApiResponse } from './client'

const BASE = ''

export interface ChatResponse {
  task_id: string
  status: string
  role: string
  content: string
  timestamp: string
  metadata: Record<string, unknown>
}

export interface TimelineEvent {
  event_type: string
  task_id: string
  step_id?: string
  tool?: string
  status?: string
  strategy?: string
  decision?: string
  reason?: string
  content?: string
  timestamp?: string
  cognitive_state?: string
  cognitive_label?: string
  metadata?: Record<string, unknown>
}

export interface ChatMessage {
  role: string
  content: string
  timestamp: string
  task_id: string
}

export type WsStatus = 'idle' | 'connected' | 'reconnecting' | 'disconnected' | 'streaming'

export async function submitChat(message: string): Promise<ApiResponse<ChatResponse>> {
  try {
    const res = await fetch(`${BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    })
    return await res.json()
  } catch (err) {
    return { success: false, data: null, error: String(err), metadata: {} }
  }
}

export async function getChatHistory(limit = 50): Promise<ApiResponse<ChatMessage[]>> {
  try {
    const res = await fetch(`${BASE}/chat/history?limit=${limit}`)
    return await res.json()
  } catch (err) {
    return { success: false, data: null, error: String(err), metadata: {} }
  }
}

export interface StreamCallbacks {
  onEvent: (event: TimelineEvent) => void
  onStatusChange: (status: WsStatus) => void
  onError?: (err: string) => void
}

export function connectChatStream(
  taskId: string,
  callbacks: StreamCallbacks,
): WebSocket {
  const { onEvent, onStatusChange, onError } = callbacks
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host

  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  const maxReconnectAttempts = 3

  function connect(): WebSocket {
    const ws = new WebSocket(`${protocol}//${host}/chat/stream`)

    ws.onopen = () => {
      onStatusChange('connected')
      ws.send(`subscribe:${taskId}`)
      // Start heartbeat
      heartbeatTimer = setInterval(() => {
        try { ws.send('ping') } catch { /* ignore */ }
      }, 15000)
      reconnectAttempts = 0
    }

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        if (data.type === 'pong') return
        if (data.event_type === 'stream_started') {
          onStatusChange('streaming')
        }
        if (data.event_type === 'stream_completed' || data.event_type === 'stream_error') {
          onStatusChange('idle')
          cleanup()
        }
        onEvent(data)
      } catch {
        // non-JSON (ping/pong)
      }
    }

    ws.onerror = () => {
      onStatusChange('disconnected')
      onError?.('WebSocket connection error')
    }

    ws.onclose = () => {
      cleanupHeartbeat()
      if (reconnectAttempts < maxReconnectAttempts) {
        onStatusChange('reconnecting')
        reconnectAttempts++
        reconnectTimer = setTimeout(() => {
          connect()
        }, 1000 * reconnectAttempts) // exponential: 1s, 2s, 3s
      } else {
        onStatusChange('disconnected')
        onError?.('WebSocket disconnected')
      }
    }

    return ws
  }

  function cleanupHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function cleanup() {
    cleanupHeartbeat()
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  return connect()
}
