import { useEffect } from 'react'
import { useSystemStore } from '../store/useSystemStore'

export default function ExecutionTimeline() {
  const { execution, loading, refresh } = useSystemStore()

  useEffect(() => {
    refresh()
  }, [refresh])

  if (loading && !execution) {
    return <div className="text-center py-20 text-gray-500">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">执行时间线</h1>

      <div className="card">
        <div className="card-title">最近执行记录</div>
        {execution && execution.length > 0 ? (
          <div className="space-y-2">
            {execution.map((item: unknown, i: number) => {
              const task = item as Record<string, unknown>
              const status = String(task.status ?? 'unknown')
              const statusColor =
                status === 'completed' ? 'bg-accent-green' :
                status === 'failed' ? 'bg-accent-red' :
                'bg-accent-yellow'

              return (
                <div key={i} className="flex items-start gap-3 p-2 rounded bg-surface-700/50">
                  <span className={`inline-block w-2 h-2 rounded-full mt-1.5 ${statusColor}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-200 truncate">
                      {String(task.input ?? task.task ?? task.task_id ?? '(empty)')}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {String(task.task_id ?? '') && <span>ID: {String(task.task_id)} · </span>}
                      {task.retry_count != null && <span>重试: {String(task.retry_count)} · </span>}
                      {String(task.status ?? '') && <span>状态: {String(task.status)}</span>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-sm text-gray-500 py-4 text-center">
            暂无执行记录
          </div>
        )}
      </div>
    </div>
  )
}
