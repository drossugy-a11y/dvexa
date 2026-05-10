import { useState } from 'react'
import { statusColor } from '../theme/runtime-colors'
import type { TimelineEvent } from '../api/chat'

interface Props {
  events: TimelineEvent[]
}

export default function ToolCallCard({ events }: Props) {
  const [expanded, setExpanded] = useState(false)
  if (events.length === 0) return null

  const anyError = events.some((e) => e.status === 'error')
  const anyRunning = events.some((e) => e.status === 'running' || !e.status)
  const groupStatus = anyRunning ? 'running' : anyError ? 'error' : 'completed'
  const groupColor = statusColor[groupStatus] ?? '#6B7280'

  return (
    <div className="border border-surface-700/40 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-secondary
                   hover:text-text-primary hover:bg-surface-750/50 transition-colors duration-fast"
      >
        <span className={`transition-transform duration-slow ${expanded ? 'rotate-90' : ''}`}>
          ▶
        </span>
        <span className="font-medium">Tool Calls</span>
        <span className="text-text-muted">{events.length}</span>
        <span className="ml-auto flex items-center gap-1">
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full ${
              anyRunning ? 'animate-pulse-subtle' : ''
            }`}
            style={{ backgroundColor: groupColor }}
          />
          <span className="text-text-muted/50">
            {anyRunning ? '⟳' : anyError ? '✗' : '✓'}
          </span>
        </span>
      </button>

      {expanded && (
        <div className="px-3 pb-2 space-y-1">
          {events.map((evt, i) => {
            const dotColor = statusColor[evt.status ?? 'pending'] ?? '#6B7280'
            return (
              <div key={i} className="flex items-start gap-2 text-[11px]">
                <span
                  className="inline-block w-1.5 h-1.5 rounded-full mt-0.5 shrink-0"
                  style={{ backgroundColor: dotColor }}
                />
                <span className="font-mono text-text-secondary">{evt.tool ?? 'unknown'}</span>
                <span className="text-text-muted/50 truncate flex-1">
                  {evt.content?.slice(0, 80) ?? ''}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
