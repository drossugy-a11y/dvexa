import { useState } from 'react'

interface Props {
  steps?: string[]
  isRunning?: boolean
}

export default function ThinkingBlock({ steps, isRunning }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!steps || steps.length === 0) {
    if (!isRunning) return null
    return (
      <div className="mt-2 text-xs text-text-muted flex items-center gap-2">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse-subtle" />
        Thinking...
      </div>
    )
  }

  return (
    <div className="mt-2 border border-surface-700/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-secondary
                   hover:text-text-primary hover:bg-surface-750/50 transition-colors duration-fast"
      >
        <span className={`transition-transform duration-slow ${expanded ? 'rotate-90' : ''}`}>
          ▶
        </span>
        <span className="font-medium">Thinking</span>
        <span className="ml-auto text-text-muted">
          {steps.length} step{steps.length > 1 ? 's' : ''}
        </span>
        {isRunning && (
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse-subtle" />
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-2 space-y-1">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px] text-text-muted">
              <span className="text-text-muted/50 mt-0.5">{i + 1}.</span>
              <span>{step}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
