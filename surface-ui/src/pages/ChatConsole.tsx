import { useEffect } from 'react'
import { useChatStore } from '../store/useChatStore'
import MessageBubble from '../components/MessageBubble'
import ThinkingBlock from '../components/ThinkingBlock'
import ChatInput from '../components/ChatInput'
import RuntimeTimeline from '../components/RuntimeTimeline'
import RuntimeDrawer from '../components/RuntimeDrawer'
import ScrollAnchor from '../components/ScrollAnchor'

export default function ChatConsole() {
  const {
    messages,
    events,
    runtimeState,
    error,
    wsStatus,
    runtimeDrawerOpen,
    sidebarVisible,
    sendMessage,
    fetchHistory,
    clearError,
    resetState,
    setRuntimeDrawerOpen,
    toggleSidebar,
  } = useChatStore()

  useEffect(() => {
    fetchHistory()
    return () => {
      // Reset state when leaving chat page
      resetState()
    }
  }, [fetchHistory, resetState])

  const isActive = runtimeState === 'submitting' || runtimeState === 'streaming'
  const eventCount = events.length

  return (
    <div className="flex h-full">
      {/* MAIN: Chat Column */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {messages.length === 0 && !isActive && runtimeState === 'idle' && (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <div className="text-3xl mb-3 text-text-muted/20">◈</div>
              <p className="text-sm text-text-muted/70 max-w-xs leading-relaxed">DVX Surface</p>
              <p className="text-xs text-text-muted/50 mt-1">Enter a task to begin</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={`msg-${i}`} message={msg}>
              {/* L1: Thinking block — only on the latest assistant message while active */}
              {msg.role === 'assistant' && i === messages.length - 1 && isActive && (
                <ThinkingBlock isRunning />
              )}
              {/* Show completed thinking block if there were steps */}
              {msg.role === 'assistant' && i === messages.length - 1 && !isActive && runtimeState === 'completed' && events.length > 0 && (
                <div className="mt-2 text-xs text-text-muted/70 flex items-center gap-1.5">
                  <span className="text-accent-green">✓</span>
                  <span>Completed</span>
                  <span className="text-text-muted/40">· {events.length} events</span>
                </div>
              )}
            </MessageBubble>
          ))}

          {/* Runtime timeline inline (when sidebar hidden) */}
          {events.length > 0 && !sidebarVisible && (
            <div className="px-4 max-w-chat mx-auto w-full">
              <RuntimeTimeline
                events={events}
                wsStatus={wsStatus}
                isRunning={isActive}
                maxHeight="300px"
              />
            </div>
          )}

          <ScrollAnchor deps={[messages, events]} />
        </div>

        {/* Error toast */}
        {error && (
          <div className="mx-4 mb-2">
            <div className="bg-semantic-danger/10 border border-semantic-danger/30 rounded-lg px-3 py-2
                            flex items-center justify-between">
              <span className="text-xs text-semantic-danger">{error}</span>
              <button
                onClick={clearError}
                className="text-semantic-danger/60 hover:text-semantic-danger ml-2
                           min-h-touch min-w-touch flex items-center justify-center"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        <ChatInput
          onSend={sendMessage}
          disabled={runtimeState !== 'idle'}
          placeholder={isActive ? 'Waiting for response...' : 'Type a message...'}
        />

        {/* Mobile: Floating runtime indicator */}
        <div className="desktop:hidden fixed right-4 bottom-20 z-50">
          <button
            onClick={() => setRuntimeDrawerOpen(true)}
            className="min-h-touch min-w-touch flex items-center justify-center
                       bg-surface-800 border border-surface-700/60 rounded-full shadow-lg
                       hover:bg-surface-750 transition-colors duration-fast"
          >
            {eventCount > 0 ? (
              <span className="relative">
                <span className={`text-sm ${isActive ? 'text-accent-green animate-pulse-subtle' : 'text-accent-primary'}`}>◉</span>
                <span className="absolute -top-1 -right-1 bg-accent-green/80
                               text-[9px] text-white rounded-full min-w-[14px] h-[14px]
                               flex items-center justify-center px-0.5">
                  {eventCount}
                </span>
              </span>
            ) : (
              <span className={`text-sm ${isActive ? 'text-accent-green animate-pulse-subtle' : 'text-text-muted'}`}>◉</span>
            )}
          </button>
        </div>

        {/* Mobile: Runtime drawer */}
        <RuntimeDrawer
          open={runtimeDrawerOpen}
          onClose={() => setRuntimeDrawerOpen(false)}
          events={events}
          wsStatus={wsStatus}
          isRunning={isActive}
        />
      </div>

      {/* DESKTOP: Runtime Sidebar */}
      <aside
        className={`hidden desktop:flex flex-col border-l border-surface-700/50
                    bg-surface-850 transition-all duration-slow ease-out overflow-hidden
                    ${sidebarVisible ? 'w-80' : 'w-0 border-l-0'}`}
      >
        {sidebarVisible && (
          <>
            <button
              onClick={toggleSidebar}
              className="absolute top-2 right-2 z-10 text-text-muted hover:text-text-secondary
                         p-1.5 rounded transition-colors duration-fast"
              title="Close sidebar"
            >
              ▶
            </button>
            <RuntimeTimeline events={events} wsStatus={wsStatus} isRunning={isActive} />
          </>
        )}
      </aside>

      {/* Desktop: Toggle sidebar button */}
      {!sidebarVisible && (
        <button
          onClick={toggleSidebar}
          className="hidden desktop:flex fixed right-0 top-1/2 -translate-y-1/2 z-10
                     bg-surface-800 border border-surface-700/50 rounded-l-lg p-2
                     text-text-muted hover:text-text-secondary hover:bg-surface-750 transition-colors duration-fast"
          title="Show runtime"
        >
          ◉
        </button>
      )}
    </div>
  )
}
