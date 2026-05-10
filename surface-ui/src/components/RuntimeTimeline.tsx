import { useRef, useEffect } from 'react'
import type { TimelineEvent } from '../api/chat'
import TimelineEventCard from './TimelineEvent'
import ToolCallCard from './ToolCallCard'
import StreamStatus from './StreamStatus'

interface Props {
  events: TimelineEvent[]
  wsStatus: 'connected' | 'reconnecting' | 'disconnected' | 'streaming' | 'idle'
  isRunning: boolean
  maxHeight?: string
}

export default function RuntimeTimeline({ events, wsStatus, isRunning, maxHeight }: Props) {
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [events])

  const grouped = groupEvents(events)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-4 py-3 border-b border-surface-700/50">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider">
            Runtime
          </h3>
          <StreamStatus status={wsStatus} />
        </div>
        {isRunning && (
          <div className="mt-1.5 h-0.5 bg-surface-700/50 rounded-full overflow-hidden">
            <div className="h-full bg-accent-green/60 rounded-full animate-stream-pulse w-1/3" />
          </div>
        )}
      </div>

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
            return <TimelineEventCard key={`evt-${i}`} event={item.event} />
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
