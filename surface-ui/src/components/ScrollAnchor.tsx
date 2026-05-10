import { useRef, useEffect, useCallback, useState } from 'react'

interface Props {
  deps: unknown[]
  disabled?: boolean
  className?: string
}

export default function ScrollAnchor({ deps, disabled, className }: Props) {
  const anchorRef = useRef<HTMLDivElement>(null)
  const [userScrolled, setUserScrolled] = useState(false)
  const containerRef = useRef<HTMLElement | null>(null)

  // Find scrollable parent
  useEffect(() => {
    const el = anchorRef.current?.parentElement
    if (!el) return

    const scrollable = el.closest('.overflow-y-auto') as HTMLElement | null
    containerRef.current = scrollable
  }, [])

  // Detect manual scroll
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const onScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 80
      if (userScrolled && isNearBottom) {
        setUserScrolled(false)
      } else if (!isNearBottom) {
        setUserScrolled(true)
      }
    }

    container.addEventListener('scroll', onScroll, { passive: true })
    return () => container.removeEventListener('scroll', onScroll)
  }, [userScrolled])

  // Auto-scroll on new content
  useEffect(() => {
    if (disabled || userScrolled) return
    anchorRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [deps, disabled, userScrolled])

  const scrollToBottom = useCallback(() => {
    setUserScrolled(false)
    anchorRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  return (
    <>
      <div ref={anchorRef} className={className} />
      {userScrolled && (
        <div className="flex justify-center">
          <button
            onClick={scrollToBottom}
            className="absolute bottom-4 bg-surface-700 hover:bg-surface-600
                       text-gray-400 text-xs px-3 py-1.5 rounded-full
                       border border-surface-600 transition-colors shadow-lg"
          >
            ↓ Scroll to bottom
          </button>
        </div>
      )}
    </>
  )
}
