/* Runtime Event Colors — 运行时事件视觉层级与颜色

层级规则：
  L0: User/AI Messages — 最高优先级
  L1: Thinking/Reasoning — 次级
  L2: Tool Execution — 弱强调
  L3: Governance Events — 低饱和
  L4: Optimization/Debug — 最弱
*/

import { color } from './tokens'

/* Runtime 事件类型 → 颜色映射 */
export const runtimeEventColor: Record<string, string> = {
  planning_started: color.accent.blue,
  governance_decision: color.accent.purple,
  tool_execution: color.accent.green,
  memory_hit: color.accent.yellow,
  execution_complete: color.accent.green,
  error: color.semantic.danger,
  optimization: color.accent.purple,
  drift: color.accent.orange,
}

/* Runtime 事件类型 → 层级 (0-4) */
export const runtimeEventLevel: Record<string, number> = {
  planning_started: 1,
  governance_decision: 3,
  tool_execution: 2,
  memory_hit: 2,
  execution_complete: 0,
  error: 0,
  optimization: 4,
  drift: 3,
}

/* 层级 → 视觉参数 */
export const levelStyle: Record<number, { fontSize: string; opacity: number; borderWidth: string }> = {
  0: { fontSize: '14px', opacity: 1.0, borderWidth: '0' },
  1: { fontSize: '13px', opacity: 0.9, borderWidth: '2px' },
  2: { fontSize: '12px', opacity: 0.85, borderWidth: '2px' },
  3: { fontSize: '11px', opacity: 0.75, borderWidth: '1px' },
  4: { fontSize: '11px', opacity: 0.6, borderWidth: '1px' },
}

/* Status → 视觉映射 */
export const statusColor: Record<string, string> = {
  running: color.accent.blue,
  completed: color.semantic.success,
  approved: color.semantic.success,
  error: color.semantic.danger,
  failed: color.semantic.danger,
  blocked: color.semantic.danger,
  degraded: color.semantic.warning,
  pending: color.text.muted,
  reconnecting: color.semantic.warning,
  disconnected: color.semantic.danger,
}

/* Cognitive 状态 → 颜色映射 */
export const cognitiveStateColor: Record<string, string> = {
  understanding: '#7C9EFF',
  analyzing: '#A78BFA',
  evaluating: '#FBBF24',
  planning: '#60A5FA',
  selecting: '#34D399',
  executing: '#F472B6',
  verifying: '#FBBF24',
  summarizing: '#60A5FA',
  completed: '#34D399',
  processing: '#6B7280',
}

/* WS 连接状态 */
export const wsStatusColor: Record<string, string> = {
  connected: color.semantic.success,
  reconnecting: color.semantic.warning,
  disconnected: color.semantic.danger,
  streaming: color.semantic.success,
  idle: color.text.muted,
}
