const WS_URL = `ws://${window.location.hostname}:8000/ws/surface`

export type WsMessage = {
  type: string
  data: Record<string, unknown>
}

export function connectWebSocket(
  onMessage: (msg: WsMessage) => void,
  onError?: (err: Event) => void,
): WebSocket {
  const ws = new WebSocket(WS_URL)

  ws.onopen = () => console.log('[Surface WS] connected')
  ws.onclose = () => console.log('[Surface WS] disconnected')
  ws.onerror = (e) => onError?.(e)
  ws.onmessage = (event) => {
    try {
      const msg: WsMessage = JSON.parse(event.data)
      onMessage(msg)
    } catch {
      console.warn('[Surface WS] invalid message')
    }
  }

  return ws
}
