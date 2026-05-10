import { NavLink } from 'react-router-dom'
import StreamStatus from './StreamStatus'
import { useChatStore } from '../store/useChatStore'

const links = [
  { to: '/', label: '仪表盘', icon: '▦' },
  { to: '/chat', label: '对话', icon: '✦' },
  { to: '/capabilities', label: '能力图谱', icon: '◈' },
  { to: '/governance', label: '治理面板', icon: '◉' },
  { to: '/execution', label: '执行时间线', icon: '▶' },
  { to: '/assimilation', label: '同化中心', icon: '◴' },
  { to: '/console', label: '控制台', icon: '〉' },
]

export default function Navbar() {
  const wsStatus = useChatStore((s) => s.wsStatus)

  return (
    <nav className="bg-surface-900/90 backdrop-blur-sm border-b border-surface-700/50 h-10 shrink-0">
      <div className="max-w-7xl mx-auto px-3 flex items-center h-full gap-4">
        <span className="text-accent-primary font-bold text-sm tracking-widest shrink-0">
          DVX
        </span>

        {/* Desktop nav */}
        <div className="hidden desktop:flex gap-0.5 flex-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-1 px-2.5 py-1 rounded text-[11px] transition-colors duration-fast ${
                  isActive
                    ? 'bg-surface-700/60 text-text-primary'
                    : 'text-text-muted hover:text-text-secondary hover:bg-surface-800/50'
                }`
              }
            >
              <span className="text-[10px]">{l.icon}</span>
              {l.label}
            </NavLink>
          ))}
        </div>

        {/* Mobile nav */}
        <div className="desktop:hidden flex flex-1 gap-0.5 overflow-x-auto no-scrollbar">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/'}
              className={({ isActive }) =>
                `shrink-0 px-2 py-1 rounded text-[11px] transition-colors duration-fast ${
                  isActive ? 'bg-surface-700/60 text-text-primary' : 'text-text-muted'
                }`
              }
            >
              {l.icon}
            </NavLink>
          ))}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <StreamStatus status={wsStatus} />
          <span className="text-[10px] text-text-muted/40">v2.6</span>
        </div>
      </div>
    </nav>
  )
}
