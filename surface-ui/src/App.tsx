import { Routes, Route, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import ChatConsole from './pages/ChatConsole'
import CapabilityGraph from './pages/CapabilityGraph'
import GovernancePanel from './pages/GovernancePanel'
import ExecutionTimeline from './pages/ExecutionTimeline'
import AssimilationCenter from './pages/AssimilationCenter'
import RuntimeConsole from './pages/RuntimeConsole'

export default function App() {
  const location = useLocation()
  const isChat = location.pathname === '/chat'

  return (
    <div className="h-full bg-surface-900 flex flex-col">
      <Navbar />
      <main
        className={
          isChat
            ? 'flex-1 flex flex-col overflow-hidden'
            : 'flex-1 p-4 max-w-7xl mx-auto w-full overflow-y-auto'
        }
      >
        <Routes>
          <Route path="/chat" element={<ChatConsole />} />
          <Route path="/" element={<Dashboard />} />
          <Route path="/capabilities" element={<CapabilityGraph />} />
          <Route path="/governance" element={<GovernancePanel />} />
          <Route path="/execution" element={<ExecutionTimeline />} />
          <Route path="/assimilation" element={<AssimilationCenter />} />
          <Route path="/console" element={<RuntimeConsole />} />
        </Routes>
      </main>
    </div>
  )
}
