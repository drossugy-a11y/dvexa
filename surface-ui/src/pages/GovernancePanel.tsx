import { useEffect } from 'react'
import { useSystemStore } from '../store/useSystemStore'
import StatusIndicator from '../components/StatusIndicator'

export default function GovernancePanel() {
  const { governance, loading, refresh } = useSystemStore()

  useEffect(() => {
    refresh()
  }, [refresh])

  if (loading && !governance) {
    return <div className="text-center py-20 text-gray-500">加载中...</div>
  }

  if (!governance) return null

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">治理面板</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="card-title">健康状态</div>
          <StatusIndicator status={governance.health_status} />
          <div className="mt-2 text-sm text-gray-400">
            评分: {governance.health_score.toFixed(2)}
          </div>
        </div>
        <div className="card">
          <div className="card-title">权限模式</div>
          <StatusIndicator status={governance.permission_mode} />
        </div>
        <div className="card">
          <div className="card-title">优化闸门</div>
          <StatusIndicator
            status={governance.can_optimize ? 'full' : 'frozen'}
            label={governance.can_optimize ? '允许优化' : '禁止优化'}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <div className="card-title">信号</div>
          {governance.signals.length > 0 ? (
            <ul className="text-sm text-gray-400 space-y-1">
              {governance.signals.map((s, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-yellow inline-block" />
                  {s}
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-sm text-gray-500">无信号</span>
          )}
        </div>
        <div className="card">
          <div className="card-title">统计</div>
          <div className="text-sm text-gray-400 space-y-1">
            <div>处理次数: {governance.process_count}</div>
            <div>快照数: {governance.snapshot_count ?? 0}</div>
            <div>技能数: {governance.skill_count ?? 0}</div>
            <div>隔离中: {(governance.quarantined ?? []).length}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
