import { useRef, useEffect, useMemo, useState } from 'react'
import type { TimelineEvent } from '../api/chat'
import TimelineEventCard from './TimelineEvent'
import ToolCallCard from './ToolCallCard'
import StreamStatus from './StreamStatus'
import { cognitiveStateColor } from '../theme/runtime-colors'

const COGNITIVE_ICONS: Record<string, string> = {
  understanding: '🧠',
  analyzing: '🔍',
  evaluating: '⚖️',
  planning: '📋',
  selecting: '🔧',
  executing: '⚡',
  verifying: '✓',
  summarizing: '💾',
  completed: '✅',
}

interface Props {
  events: TimelineEvent[]
  wsStatus: 'connected' | 'reconnecting' | 'disconnected' | 'streaming' | 'idle'
  isRunning: boolean
  maxHeight?: string
}

export default function RuntimeTimeline({ events, wsStatus, isRunning, maxHeight }: Props) {
  const listRef = useRef<HTMLDivElement>(null)
  const [debugMode, setDebugMode] = useState(false)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [events])

  const grouped = groupEvents(events)

  const currentCognitive = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i]
      if (ev.cognitive_label && ev.cognitive_state) {
        return {
          label: ev.cognitive_label,
          state: ev.cognitive_state,
          icon: COGNITIVE_ICONS[ev.cognitive_state] ?? '🧠',
          color: cognitiveStateColor[ev.cognitive_state] ?? '#6B7280',
        }
      }
    }
    return null
  }, [events])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-4 py-3 border-b border-surface-700/50">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider">
            Runtime
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDebugMode(!debugMode)}
              className={`text-[10px] px-2 py-0.5 rounded font-mono transition-colors ${
                debugMode
                  ? 'bg-accent-blue/20 text-accent-blue/80'
                  : 'text-text-muted/50 hover:text-text-muted/70'
              }`}
            >
              {debugMode ? '[debug on]' : '[debug]'}
            </button>
            <StreamStatus status={wsStatus} />
          </div>
        </div>
        {isRunning && (
          <div className="mt-1.5 h-0.5 bg-surface-700/50 rounded-full overflow-hidden">
            <div className="h-full bg-accent-green/60 rounded-full animate-stream-pulse w-1/3" />
          </div>
        )}
      </div>

      {/* Thinking Status Bar — shown when system is running and cognitive state is available */}
      {isRunning && currentCognitive && (
        <div className="shrink-0 px-4 py-2 border-b border-surface-700/30 bg-surface-800/40">
          <div className="flex items-center gap-2">
            <span className="text-sm">{currentCognitive.icon}</span>
            <span
              className="text-xs font-semibold tracking-wide animate-pulse"
              style={{ color: currentCognitive.color }}
            >
              {currentCognitive.label}
            </span>
            <span
              className="inline-block w-2 h-2 rounded-full animate-pulse ml-auto"
              style={{ backgroundColor: currentCognitive.color }}
            />
          </div>
        </div>
      )}

      {/* Event list */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto"
        style={{ maxHeight: maxHeight ?? 'none' }}
      >
        {events.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-xs text-text-muted/60">
              {isRunning ? 'Waiting for events...' : 'No active task'}
            </p>
          </div>
        )}

        <div className="p-3 space-y-1.5">
          {grouped.map((item, i) => {
            if (item.type === 'tool_group') {
              return <ToolCallCard key={`tool-${i}`} events={item.events} />
            }
            return <TimelineEventCard key={`evt-${i}`} event={item.event} debug={debugMode} />
          })}
        </div>
      </div>
    </div>
  )
}

function groupEvents(events: TimelineEvent[]) {
  const result: Array<
    { type: 'single'; event: TimelineEvent } | { type: 'tool_group'; events: TimelineEvent[] }
  > = []

  let i = 0
  while (i < events.length) {
    if (events[i].event_type === 'tool_execution') {
      const group: TimelineEvent[] = []
      while (i < events.length && events[i].event_type === 'tool_execution') {
        group.push(events[i])
        i++
      }
      if (group.length === 1) {
        result.push({ type: 'single', event: group[0] })
      } else {
        result.push({ type: 'tool_group', events: group })
      }
    } else {
      result.push({ type: 'single', event: events[i] })
      i++
    }
  }

  return result
}
