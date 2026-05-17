import type { CognitiveProfile } from '../api/client'

interface Props {
  profile: CognitiveProfile | null
}

const classificationLabels: Record<string, string> = {
  planning_heavy: '规划主导',
  execution_heavy: '执行主导',
  tool_heavy: '工具主导',
  balanced: '均衡型',
}

export default function CognitiveRatioChart({ profile }: Props) {
  if (!profile) {
    return (
      <div className="text-sm text-gray-500 py-8 text-center">
        暂无认知数据
      </div>
    )
  }

  const classification = profile.classification ?? 'unknown'
  const label = classificationLabels[classification] ?? classification

  const bars = [
    {
      key: 'planning',
      label: '规划',
      ratio: profile.planning_ratio,
      color: 'bg-accent-blue',
      bgColor: 'bg-accent-blue/20',
    },
    {
      key: 'execution',
      label: '执行',
      ratio: profile.execution_ratio,
      color: 'bg-accent-pink',
      bgColor: 'bg-accent-pink/20',
    },
    {
      key: 'tool',
      label: '工具',
      ratio: profile.tool_ratio,
      color: 'bg-accent-green',
      bgColor: 'bg-accent-green/20',
    },
  ]

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-sm text-gray-400">认知分类:</span>
        <span className="text-sm font-medium text-white">{label}</span>
      </div>

      <div className="space-y-3">
        {bars.map((bar) => {
          const pct = (bar.ratio * 100).toFixed(1)
          return (
            <div key={bar.key}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-400">{bar.label}</span>
                <span className="text-gray-500">{pct}%</span>
              </div>
              <div className={`w-full h-3 rounded-full ${bar.bgColor} overflow-hidden`}>
                <div
                  className={`h-full rounded-full ${bar.color} transition-all duration-500`}
                  style={{ width: `${Math.min(bar.ratio * 100, 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
