import { runtimeEventColor, runtimeEventLevel, levelStyle, statusColor } from '../theme/runtime-colors'
import type { TimelineEvent as TimelineEventType } from '../api/chat'

const EVENT_ICONS: Record<string, string> = {
  planning_started: '🧠',
  governance_decision: '⚖️',
  tool_execution: '🔧',
  memory_hit: '💾',
  execution_complete: '✅',
  error: '❌',
}

const EVENT_LABELS: Record<string, string> = {
  planning_started: 'Planning',
  governance_decision: 'Governance',
  tool_execution: 'Tool',
  memory_hit: 'Memory',
  execution_complete: 'Complete',
  error: 'Error',
}

interface Props {
  event: TimelineEventType
}

export default function TimelineEvent({ event }: Props) {
  const accentColor = runtimeEventColor[event.event_type] ?? '#6B7280'
  const level = runtimeEventLevel[event.event_type] ?? 2
  const style = levelStyle[level]
  const statusDot = event.status ? (statusColor[event.status] ?? '#6B7280') : ''
  const icon = EVENT_ICONS[event.event_type] ?? '📋'
  const label = EVENT_LABELS[event.event_type] ?? event.event_type

  return (
    <div
      className="rounded-lg px-3 py-2 border"
      style={{
        borderColor: `${accentColor}20`,
        borderLeftWidth: style.borderWidth,
        borderLeftColor: `${accentColor}40`,
        opacity: style.opacity,
        fontSize: style.fontSize,
      }}
    >
      <div className="flex items-center gap-1.5">
        <span>{icon}</span>
        <span className="font-medium text-text-primary/80">{label}</span>
        {event.status && (
          <span className="ml-auto flex items-center gap-1">
            {statusDot && (
              <span
                className="inline-block w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: statusDot }}
              />
            )}
            <span className="text-[10px] px-1.5 py-0.5 rounded font-medium text-text-muted/70">
              {event.status}
            </span>
          </span>
        )}
      </div>

      {event.tool && (
        <div className="text-[11px] text-text-muted/70 mt-1 font-mono">{event.tool}</div>
      )}
      {event.strategy && (
        <div className="text-[11px] text-text-muted/60 mt-1">
          {event.strategy}
          {event.decision && <span className="text-text-muted/40"> → {event.decision}</span>}
        </div>
      )}
      {event.content && (
        <div className="text-[11px] text-text-muted/50 mt-1 leading-relaxed line-clamp-2">
          {event.content}
        </div>
      )}
      {event.reason && (
        <div className="text-[11px] text-text-muted/40 mt-0.5 italic">{event.reason}</div>
      )}
      {event.timestamp && (
        <div className="text-[10px] text-text-muted/30 mt-1">{event.timestamp}</div>
      )}
    </div>
  )
}
