import { useEffect } from 'react'
import RuntimeTimeline from './RuntimeTimeline'
import type { TimelineEvent } from '../api/chat'

interface Props {
  open: boolean
  onClose: () => void
  events: TimelineEvent[]
  wsStatus: 'connected' | 'reconnecting' | 'disconnected' | 'streaming' | 'idle'
  isRunning: boolean
}

export default function RuntimeDrawer({ open, onClose, events, wsStatus, isRunning }: Props) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 z-[90] desktop:hidden"
        onClick={onClose}
      />
      <div
        className="fixed bottom-0 left-0 right-0 z-[100] max-h-[70vh] desktop:hidden
                   bg-surface-900 border-t border-surface-700 rounded-t-2xl
                   transform transition-transform duration-slow ease-out
                   overflow-hidden"
      >
        <div className="flex justify-center pt-2 pb-1">
          <div className="w-10 h-1 rounded-full bg-surface-600" />
        </div>
        <div className="absolute top-2 right-3">
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-secondary text-lg
                       min-h-touch min-w-touch flex items-center justify-center"
          >
            ✕
          </button>
        </div>
        <div className="h-[calc(70vh-40px)]">
          <RuntimeTimeline events={events} wsStatus={wsStatus} isRunning={isRunning} />
        </div>
      </div>
    </>
  )
}
