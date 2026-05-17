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

// ─── Intelligence API ────────────────────────────────────────────────────

export interface IntelligenceReport {
  status: string
  report?: {
    total_traces: number
    success_count: number
    failure_count: number
    avg_duration_ms: number
    retry_rate: number
    governance_block_rate: number
    stage_durations?: Record<string, number>
    strategy_distribution?: Record<string, number>
    mode_distribution?: Record<string, number>
    error_types?: Record<string, number>
  }
}

export interface FailurePatternData {
  pattern_type: string
  severity: number
  description: string
  suggestion?: string
  trace_ids: string[]
}

export interface CognitiveProfile {
  planning_ratio: number
  execution_ratio: number
  tool_ratio: number
  classification: string
}

export async function getIntelligenceReport(): Promise<IntelligenceReport> {
  const res = await fetch('/surface/intelligence/report')
  return res.json()
}

export async function getFailurePatterns(): Promise<{
  status: string
  patterns: FailurePatternData[]
}> {
  const res = await fetch('/surface/intelligence/patterns')
  return res.json()
}

export async function getCognitiveProfile(): Promise<{
  status: string
  profile: CognitiveProfile
}> {
  const res = await fetch('/surface/intelligence/cognitive')
  return res.json()
}
