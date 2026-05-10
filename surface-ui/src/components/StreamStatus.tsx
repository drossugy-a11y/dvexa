import { wsStatusColor } from '../theme/runtime-colors'

interface Props {
  status: 'connected' | 'reconnecting' | 'disconnected' | 'streaming' | 'idle'
  label?: boolean
}

const labels: Record<string, string> = {
  connected: 'Connected',
  reconnecting: 'Reconnecting',
  disconnected: 'Disconnected',
  streaming: 'Streaming',
  idle: 'Idle',
}

export default function StreamStatus({ status, label: showLabel = true }: Props) {
  const dotColor = wsStatusColor[status] ?? wsStatusColor.idle
  const isPulsing = status === 'reconnecting' || status === 'streaming'

  return (
    <span className="inline-flex items-center gap-1.5" title={labels[status] ?? status}>
      <span
        className={`inline-block w-2 h-2 rounded-full transition-colors duration-normal
                    ${isPulsing ? 'animate-pulse-subtle' : ''}`}
        style={{ backgroundColor: dotColor }}
      />
      {showLabel && <span className="text-[11px] text-text-muted">{labels[status] ?? status}</span>}
    </span>
  )
}
