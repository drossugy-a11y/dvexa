import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import CapabilityGraph from './pages/CapabilityGraph'
import GovernancePanel from './pages/GovernancePanel'
import ExecutionTimeline from './pages/ExecutionTimeline'
import AssimilationCenter from './pages/AssimilationCenter'
import RuntimeConsole from './pages/RuntimeConsole'

export default function App() {
  return (
    <div className="min-h-screen bg-surface-900">
      <Navbar />
      <main className="p-4 max-w-7xl mx-auto">
        <Routes>
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
