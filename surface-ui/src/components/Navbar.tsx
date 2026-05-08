import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: '仪表盘', icon: '▦' },
  { to: '/capabilities', label: '能力图谱', icon: '◈' },
  { to: '/governance', label: '治理面板', icon: '◉' },
  { to: '/execution', label: '执行时间线', icon: '▶' },
  { to: '/assimilation', label: '同化中心', icon: '◴' },
  { to: '/console', label: '控制台', icon: '〉' },
]

export default function Navbar() {
  return (
    <nav className="bg-surface-800 border-b border-surface-600">
      <div className="max-w-7xl mx-auto px-4 flex items-center h-12 gap-6">
        <span className="text-accent-purple font-bold text-lg tracking-wider">
          DVX Surface
        </span>
        <div className="flex gap-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-surface-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-surface-700'
                }`
              }
            >
              <span className="text-xs">{l.icon}</span>
              {l.label}
            </NavLink>
          ))}
        </div>
        <div className="ml-auto text-xs text-gray-500">v1.0</div>
      </div>
    </nav>
  )
}
