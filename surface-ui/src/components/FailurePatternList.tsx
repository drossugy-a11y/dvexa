import type { FailurePatternData } from '../api/client'

interface Props {
  patterns: FailurePatternData[]
}

const severityColors: Record<string, string> = {
  repeat_failure: 'bg-accent-red',
  flaky_path: 'bg-accent-yellow',
  governance_block: 'bg-accent-orange',
  escalating_risk: 'bg-accent-red',
  stalled_recovery: 'bg-accent-red',
  retry_storm: 'bg-accent-red',
}

const severityLabels: Record<string, string> = {
  repeat_failure: '重复失败',
  flaky_path: '不稳定路径',
  governance_block: '治理阻塞',
  escalating_risk: '风险升级',
  stalled_recovery: '恢复停滞',
  retry_storm: '重试风暴',
}

export default function FailurePatternList({ patterns }: Props) {
  if (!patterns || patterns.length === 0) {
    return (
      <div className="text-sm text-gray-500 py-8 text-center">
        未检测到故障模式
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {patterns.map((p, i) => {
        const color = severityColors[p.pattern_type] ?? 'bg-gray-500'
        const label = severityLabels[p.pattern_type] ?? p.pattern_type
        const sevPct = (p.severity * 100).toFixed(0)

        return (
          <div key={i} className="flex items-start gap-3 p-2.5 rounded bg-surface-700/40 border border-surface-600/30">
            <span className={`inline-block w-2 h-2 rounded-full mt-1.5 shrink-0 ${color}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded ${color}`}>
                  {label}
                </span>
                <span className="text-[11px] text-gray-500">{sevPct}% severity</span>
              </div>
              <div className="text-sm text-gray-300">{p.description}</div>
              {p.trace_ids && p.trace_ids.length > 0 && (
                <div className="text-[11px] text-gray-500 mt-1">
                  影响 {p.trace_ids.length} 条轨迹
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
