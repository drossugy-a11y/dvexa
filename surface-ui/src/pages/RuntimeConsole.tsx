import { useEffect, useState } from 'react'

export default function RuntimeConsole() {
  const [logs, setLogs] = useState<string[]>([])
  const [input, setInput] = useState('')

  const addLog = (msg: string) => {
    setLogs((prev) => [...prev.slice(-99), `[${new Date().toLocaleTimeString()}] ${msg}`])
  }

  useEffect(() => {
    addLog('DVX Surface 控制台已连接')
    addLog('服务: http://localhost:8000')

    let ws: WebSocket | null = null
    try {
      ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/surface`)
      ws.onopen = () => addLog('WebSocket 已连接')
      ws.onmessage = (e) => addLog(`WS → ${e.data.slice(0, 200)}`)
      ws.onclose = () => addLog('WebSocket 已断开')
      ws.onerror = () => addLog('WebSocket 错误')
    } catch {
      addLog('WebSocket 连接失败 (服务未启动 ?)')
    }

    return () => { ws?.close() }
  }, [])

  const handleCommand = async () => {
    if (!input.trim()) return
    const cmd = input.trim()
    setInput('')
    addLog(`→ ${cmd}`)

    try {
      const res = await fetch('/health')
      const data = await res.json()
      addLog(`← health: ${JSON.stringify(data)}`)
    } catch (err) {
      addLog(`← error: ${String(err)}`)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-white">运行时控制台</h1>

      <div className="card">
        <div className="card-title mb-2">日志</div>
        <div className="bg-black rounded p-3 h-96 overflow-y-auto font-mono text-xs space-y-0.5">
          {logs.map((line, i) => (
            <div key={i} className="text-gray-400 hover:text-gray-200">
              {line}
            </div>
          ))}
          {logs.length === 0 && <div className="text-gray-600">等待日志...</div>}
        </div>
      </div>

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCommand()}
          placeholder="输入命令 (如: health)"
          className="flex-1 bg-surface-800 border border-surface-600 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
        />
        <button
          onClick={handleCommand}
          className="px-4 py-2 bg-accent-blue rounded text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          发送
        </button>
      </div>
    </div>
  )
}
