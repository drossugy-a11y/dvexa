const BASE = ''

export interface ApiResponse<T> {
  success: boolean
  data: T | null
  error: string | null
  metadata: Record<string, unknown>
}

async function fetchJson<T>(url: string): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${BASE}${url}`)
    return await res.json()
  } catch (err) {
    return { success: false, data: null, error: String(err), metadata: {} }
  }
}

export interface SystemSnapshot {
  timestamp: string
  task_count: number
  system_health: string
  capability_summary: Record<string, unknown>
  evolution_report: Record<string, unknown>
  governance_status: Record<string, unknown>
  execution_history: unknown[]
  insight_report: Record<string, unknown>
  metric_summary: Record<string, unknown>
}

export interface GovernanceStatus {
  health_score: number
  health_status: string
  permission_mode: string
  can_optimize: boolean
  drift_detected: boolean
  lock_active: boolean
  signals: string[]
  process_count: number
  skill_count?: number
  snapshot_count?: number
  quarantined?: string[]
}

export interface CapabilitySummary {
  total: number
  by_category: Record<string, number>
  by_maturity: Record<string, number>
}

export function getSnapshot(): Promise<ApiResponse<SystemSnapshot>> {
  return fetchJson<SystemSnapshot>('/surface/snapshot')
}

export function getCapabilities(): Promise<ApiResponse<Record<string, unknown>>> {
  return fetchJson('/surface/capabilities')
}

export function getGovernance(): Promise<ApiResponse<GovernanceStatus>> {
  return fetchJson<GovernanceStatus>('/surface/governance')
}

export function getEvolution(): Promise<ApiResponse<Record<string, unknown>>> {
  return fetchJson('/surface/evolution')
}

export function getInsight(): Promise<ApiResponse<Record<string, unknown>>> {
  return fetchJson('/surface/insight')
}

export function getMetrics(): Promise<ApiResponse<Record<string, unknown>>> {
  return fetchJson('/surface/metrics')
}

export function getExecution(): Promise<ApiResponse<unknown[]>> {
  return fetchJson('/surface/execution')
}
