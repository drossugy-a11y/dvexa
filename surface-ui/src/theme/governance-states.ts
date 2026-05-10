/* Governance State Theme — 治理状态颜色映射

只影响局部 UI 元素（Badge / Border / Indicator），
不改变整体页面色调。
*/

export interface GovernanceTheme {
  badgeBg: string
  badgeText: string
  badgeBorder: string
  indicatorBg: string
  glow: string
}

/* 策略 → 主题 */
export const governanceTheme: Record<string, GovernanceTheme> = {
  BALANCED: {
    badgeBg: 'rgba(124, 158, 255, 0.12)',
    badgeText: '#7C9EFF',
    badgeBorder: 'rgba(124, 158, 255, 0.3)',
    indicatorBg: '#7C9EFF',
    glow: 'none',
  },
  STRICT: {
    badgeBg: 'rgba(251, 191, 36, 0.12)',
    badgeText: '#FBBF24',
    badgeBorder: 'rgba(251, 191, 36, 0.3)',
    indicatorBg: '#FBBF24',
    glow: 'none',
  },
  CONSERVATIVE: {
    badgeBg: 'rgba(34, 211, 238, 0.1)',
    badgeText: '#22D3EE',
    badgeBorder: 'rgba(34, 211, 238, 0.25)',
    indicatorBg: '#22D3EE',
    glow: 'none',
  },
  EXPLORATION: {
    badgeBg: 'rgba(167, 139, 250, 0.12)',
    badgeText: '#A78BFA',
    badgeBorder: 'rgba(167, 139, 250, 0.3)',
    indicatorBg: '#A78BFA',
    glow: '0 0 8px rgba(167, 139, 250, 0.2)',
  },
  ROLLBACK: {
    badgeBg: 'rgba(248, 113, 113, 0.12)',
    badgeText: '#F87171',
    badgeBorder: 'rgba(248, 113, 113, 0.3)',
    indicatorBg: '#F87171',
    glow: 'none',
  },
  OPTIMIZED: {
    badgeBg: 'rgba(74, 222, 128, 0.12)',
    badgeText: '#4ADE80',
    badgeBorder: 'rgba(74, 222, 128, 0.3)',
    indicatorBg: '#4ADE80',
    glow: 'none',
  },
  DRIFT_DETECTED: {
    badgeBg: 'rgba(251, 146, 60, 0.12)',
    badgeText: '#FB923C',
    badgeBorder: 'rgba(251, 146, 60, 0.3)',
    indicatorBg: '#FB923C',
    glow: 'none',
  },
}

export const defaultGovernance: GovernanceTheme = {
  badgeBg: 'rgba(106, 115, 134, 0.15)',
  badgeText: '#9AA4B2',
  badgeBorder: 'rgba(106, 115, 134, 0.25)',
  indicatorBg: '#6B7280',
  glow: 'none',
}

export function getGovernanceTheme(strategy?: string): GovernanceTheme {
  if (!strategy) return defaultGovernance
  return governanceTheme[strategy] ?? defaultGovernance
}
