import { useEffect } from 'react'
import { useSystemStore } from '../store/useSystemStore'

export default function CapabilityGraph() {
  const { capabilities, loading, refresh } = useSystemStore()

  useEffect(() => {
    refresh()
  }, [refresh])

  const summary = capabilities?.summary as Record<string, unknown> | undefined
  const byCategory = summary?.by_category as Record<string, number> | undefined
  const byMaturity = summary?.by_maturity as Record<string, number> | undefined

  if (loading && !capabilities) {
    return <div className="text-center py-20 text-gray-500">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">能力图谱</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="card-title">按分类</div>
          {byCategory && (
            <div className="space-y-2">
              {Object.entries(byCategory).map(([cat, count]) => (
                <div key={cat} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300 capitalize">{cat}</span>
                  <div className="flex items-center gap-2">
                    <div
                      className="h-2 rounded bg-accent-blue"
                      style={{ width: `${Math.min(100, (count / Math.max(...Object.values(byCategory))) * 100)}px` }}
                    />
                    <span className="text-sm text-gray-400 w-6 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-title">按成熟度</div>
          {byMaturity && (
            <div className="space-y-2">
              {Object.entries(byMaturity).map(([mat, count]) => (
                <div key={mat} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300 capitalize">{mat}</span>
                  <span className="text-sm text-gray-400">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title">完整数据</div>
        <pre className="text-xs text-gray-400 overflow-auto max-h-64">
          {JSON.stringify(capabilities, null, 2)}
        </pre>
      </div>
    </div>
  )
}
