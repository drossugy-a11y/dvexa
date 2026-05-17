import MetricCard from './MetricCard'
import type { IntelligenceReport } from '../api/client'

interface Props {
  report: IntelligenceReport | null
}

export default function ExecutionHeatmap({ report }: Props) {
  if (!report || report.status !== 'ok' || !report.report) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard title="总轨迹数" value="--" status="blue" />
        <MetricCard title="成功率" value="--" status="blue" />
        <MetricCard title="平均耗时" value="--" status="blue" />
        <MetricCard title="重试率" value="--" status="blue" />
        <MetricCard title="治理阻塞率" value="--" status="blue" />
        <MetricCard title="失败数" value="--" status="blue" />
      </div>
    )
  }

  const r = report.report
  const successRate =
    r.total_traces > 0 ? ((r.success_count / r.total_traces) * 100).toFixed(1) : '0.0'
  const rateStatus =
    parseFloat(successRate) >= 80
      ? 'green'
      : parseFloat(successRate) >= 50
        ? 'yellow'
        : 'red'

  const retryPct = (r.retry_rate * 100).toFixed(1)
  const retryStatus = parseFloat(retryPct) < 20 ? 'green' : parseFloat(retryPct) < 50 ? 'yellow' : 'red'

  const govBlockPct = (r.governance_block_rate * 100).toFixed(1)
  const govStatus = parseFloat(govBlockPct) < 10 ? 'green' : parseFloat(govBlockPct) < 30 ? 'yellow' : 'red'

  const avgDurationMs = r.avg_duration_ms.toFixed(0)
  const durStatus = r.avg_duration_ms < 1000 ? 'green' : r.avg_duration_ms < 5000 ? 'yellow' : 'red'

  const failStatus = r.failure_count === 0 ? 'green' : r.failure_count < 5 ? 'yellow' : 'red'

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <MetricCard title="总轨迹数" value={r.total_traces} status="blue" />
      <MetricCard
        title="成功率"
        value={`${successRate}%`}
        subtitle={`${r.success_count} / ${r.total_traces}`}
        status={rateStatus}
      />
      <MetricCard title="平均耗时" value={`${avgDurationMs}ms`} status={durStatus} />
      <MetricCard title="重试率" value={`${retryPct}%`} status={retryStatus} />
      <MetricCard
        title="治理阻塞率"
        value={`${govBlockPct}%`}
        status={govStatus}
      />
      <MetricCard title="失败数" value={r.failure_count} status={failStatus} />
    </div>
  )
}
