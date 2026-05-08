import { useEffect } from 'react'
import { useSystemStore } from '../store/useSystemStore'

export default function AssimilationCenter() {
  const { evolution, loading, refresh } = useSystemStore()

  useEffect(() => {
    refresh()
  }, [refresh])

  if (loading && !evolution) {
    return <div className="text-center py-20 text-gray-500">加载中...</div>
  }

  const events = evolution?.total_events as number ?? 0
  const byType = evolution?.by_event_type as Record<string, number> | undefined
  const adopted = evolution?.adopted_capabilities as string[] | undefined

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">同化中心</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="card-title">总事件数</div>
          <div className="metric-value">{events}</div>
        </div>
        <div className="card">
          <div className="card-title">已采纳</div>
          <div className="metric-value">{adopted?.length ?? 0}</div>
        </div>
        <div className="card">
          <div className="card-title">失败数</div>
          <div className="metric-value">{evolution?.failure_count as number ?? 0}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="card-title">按事件类型</div>
          {byType ? (
            <div className="space-y-2">
              {Object.entries(byType).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">{type}</span>
                  <span className="text-sm text-gray-400">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-500">无数据</div>
          )}
        </div>

        <div className="card">
          <div className="card-title">已采纳能力</div>
          {adopted && adopted.length > 0 ? (
            <ul className="text-sm text-gray-400 space-y-1">
              {adopted.map((c, i) => (
                <li key={i} className="truncate">{c}</li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-gray-500">暂无已采纳能力</div>
          )}
        </div>
      </div>
    </div>
  )
}
