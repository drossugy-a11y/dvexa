import { useEffect } from 'react'
import { useSystemStore } from '../store/useSystemStore'
import MetricCard from '../components/MetricCard'
import StatusIndicator from '../components/StatusIndicator'

export default function Dashboard() {
  const { snapshot, governance, metrics, loading, refresh } = useSystemStore()

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  if (loading && !snapshot) {
    return <div className="text-center py-20 text-gray-500">加载中...</div>
  }

  const gov = governance
  const healthStatus = snapshot?.system_health ?? 'unknown'
  const permMode = gov?.permission_mode ?? 'unknown'
  const canOpt = gov?.can_optimize

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">系统概览</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard title="系统健康" value="" status={healthStatus === 'healthy' ? 'green' : 'yellow'}>
          <StatusIndicator status={healthStatus} />
        </MetricCard>
        <MetricCard
          title="任务总数"
          value={snapshot?.task_count ?? 0}
          status="blue"
        />
        <MetricCard
          title="权限模式"
          value={permMode}
          status={permMode === 'FULL' ? 'green' : permMode === 'LIMITED' ? 'yellow' : 'red'}
        />
        <MetricCard
          title="优化闸门"
          value={canOpt ? '开启' : '关闭'}
          status={canOpt ? 'green' : 'red'}
        />
        <MetricCard
          title="健康评分"
          value={gov?.health_score?.toFixed(2) ?? '—'}
          status={(gov?.health_score ?? 1) >= 0.8 ? 'green' : (gov?.health_score ?? 1) >= 0.6 ? 'yellow' : 'red'}
        />
        <MetricCard
          title="处理次数"
          value={gov?.process_count ?? 0}
          status="blue"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="card-title">能力分布</div>
          {snapshot?.capability_summary && (
            <pre className="text-xs text-gray-400 overflow-auto max-h-48">
              {JSON.stringify(snapshot.capability_summary, null, 2)}
            </pre>
          )}
        </div>
        <div className="card">
          <div className="card-title">指标摘要</div>
          {metrics && (
            <pre className="text-xs text-gray-400 overflow-auto max-h-48">
              {JSON.stringify(metrics, null, 2)}
            </pre>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title">信号</div>
        {gov?.signals && gov.signals.length > 0 ? (
          <div className="flex gap-2 flex-wrap">
            {gov.signals.map((s, i) => (
              <span
                key={i}
                className="badge bg-surface-600 text-gray-300"
              >
                {s}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-sm text-gray-500">无活跃信号</span>
        )}
      </div>
    </div>
  )
}
