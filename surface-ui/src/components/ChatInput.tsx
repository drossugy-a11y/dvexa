import { useState, useRef, useEffect } from 'react'

interface Props {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

export default function ChatInput({ onSend, disabled, placeholder }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 160) + 'px'
    }
  }, [value])

  const handleSend = () => {
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div
      className="border-t border-surface-700/50 bg-surface-900/95 backdrop-blur-sm
                 pb-[env(safe-area-inset-bottom,0px)]"
    >
      <div className="max-w-chat mx-auto px-4 py-3">
        <div className="flex items-end gap-2 bg-surface-800 border border-surface-700/60
                        rounded-xl px-4 py-2 focus-within:border-accent-primary/40 transition-colors duration-fast">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder ?? 'Type a message...'}
            disabled={disabled}
            rows={1}
            className="flex-1 bg-transparent text-sm text-text-primary placeholder-text-muted/50
                       resize-none outline-none max-h-[160px] leading-relaxed
                       disabled:opacity-40"
          />
          <button
            onClick={handleSend}
            disabled={disabled || !value.trim()}
            className="shrink-0 min-h-touch min-w-touch flex items-center justify-center rounded-lg
                       bg-accent-primary/20 hover:bg-accent-primary/30 disabled:bg-surface-700
                       disabled:text-text-muted/40 text-accent-primary transition-colors duration-fast
                       text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-primary/50"
          >
            ↵
          </button>
        </div>
        {disabled && (
          <div className="text-[11px] text-text-muted/50 text-center mt-1.5">
            Waiting for response...
          </div>
        )}
      </div>
    </div>
  )
}
