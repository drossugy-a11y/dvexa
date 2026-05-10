import type { ChatMessage } from '../api/chat'

interface Props {
  message: ChatMessage
  children?: React.ReactNode
}

export default function MessageBubble({ message, children }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} px-4`}>
      <div
        className={`max-w-[88%] desktop:max-w-[720px] rounded-xl px-4 py-3 ${
          isUser
            ? 'bg-accent-primary/15 text-text-primary rounded-br-md border border-accent-primary/20'
            : 'bg-surface-800/80 text-text-primary rounded-bl-md border border-surface-700/50'
        }`}
      >
        <div className="text-[11px] text-text-muted mb-1.5 tracking-wide">
          {isUser ? 'You' : 'DVexa'}
          {message.timestamp && ` · ${message.timestamp}`}
        </div>
        <div className="text-sm leading-relaxed whitespace-pre-wrap break-words text-text-primary/90">
          {message.content}
        </div>
        {children}
      </div>
    </div>
  )
}
