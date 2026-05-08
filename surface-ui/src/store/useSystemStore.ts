import { create } from 'zustand'
import {
  getSnapshot,
  getCapabilities,
  getGovernance,
  getEvolution,
  getInsight,
  getMetrics,
  getExecution,
  type SystemSnapshot,
  type GovernanceStatus,
} from '../api/client'

interface SystemState {
  snapshot: SystemSnapshot | null
  governance: GovernanceStatus | null
  capabilities: Record<string, unknown> | null
  evolution: Record<string, unknown> | null
  insight: Record<string, unknown> | null
  metrics: Record<string, unknown> | null
  execution: unknown[] | null
  loading: boolean
  error: string | null
  lastUpdate: number

  refresh: () => Promise<void>
}

export const useSystemStore = create<SystemState>((set) => ({
  snapshot: null,
  governance: null,
  capabilities: null,
  evolution: null,
  insight: null,
  metrics: null,
  execution: null,
  loading: false,
  error: null,
  lastUpdate: 0,

  refresh: async () => {
    set({ loading: true, error: null })
    try {
      const [snapRes, govRes, capRes, evoRes, insRes, metRes, execRes] =
        await Promise.all([
          getSnapshot(),
          getGovernance(),
          getCapabilities(),
          getEvolution(),
          getInsight(),
          getMetrics(),
          getExecution(),
        ])
      set({
        snapshot: snapRes.data,
        governance: govRes.data,
        capabilities: capRes.data,
        evolution: evoRes.data,
        insight: insRes.data,
        metrics: metRes.data,
        execution: execRes.data as unknown[],
        loading: false,
        lastUpdate: Date.now(),
      })
    } catch (err) {
      set({ loading: false, error: String(err) })
    }
  },
}))
