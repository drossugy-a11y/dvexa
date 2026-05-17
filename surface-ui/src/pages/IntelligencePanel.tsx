import { useEffect, useState } from 'react'
import {
  getIntelligenceReport,
  getFailurePatterns,
  getCognitiveProfile,
  type IntelligenceReport,
  type FailurePatternData,
  type CognitiveProfile,
} from '../api/client'
import ExecutionHeatmap from '../components/ExecutionHeatmap'
import FailurePatternList from '../components/FailurePatternList'
import CognitiveRatioChart from '../components/CognitiveRatioChart'

export default function IntelligencePanel() {
  const [report, setReport] = useState<IntelligenceReport | null>(null)
  const [patterns, setPatterns] = useState<FailurePatternData[]>([])
  const [profile, setProfile] = useState<CognitiveProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchAll() {
      setLoading(true)
      setError(null)
      try {
        const [reportRes, patternsRes, profileRes] = await Promise.all([
          getIntelligenceReport(),
          getFailurePatterns(),
          getCognitiveProfile(),
        ])
        if (cancelled) return

        setReport(reportRes)
        setPatterns(
          patternsRes.status === 'ok' ? patternsRes.patterns : [],
        )
        setProfile(
          profileRes.status === 'ok' ? profileRes.profile : null,
        )
      } catch (err) {
        if (!cancelled) {
          setError(String(err))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchAll()
    return () => {
      cancelled = true
    }
  }, [])

  // ── Loading state ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold text-white">智能分析</h1>
        <div className="text-center py-20 text-gray-500">加载中...</div>
      </div>
    )
  }

  // ── Error state ────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold text-white">智能分析</h1>
        <div className="card border-l-4 border-l-accent-red">
          <div className="card-title text-accent-red">加载失败</div>
          <div className="text-sm text-gray-400 mt-1">{error}</div>
        </div>
      </div>
    )
  }

  // ── Empty state ────────────────────────────────────────────────────────
  const hasData = report?.status === 'ok' || patterns.length > 0 || profile !== null
  if (!hasData) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold text-white">智能分析</h1>
        <div className="card">
          <div className="text-sm text-gray-500 py-8 text-center">
            暂无智能分析数据
          </div>
        </div>
      </div>
    )
  }

  // ── Main content ───────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">智能分析</h1>

      {/* Section 1: Execution Heatmap */}
      <section>
        <h2 className="text-sm font-semibold text-gray-300 mb-3">执行分析</h2>
        <ExecutionHeatmap report={report} />
      </section>

      {/* Section 2: Cognitive Profile + Failure Patterns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="card-title">认知剖面</div>
          <CognitiveRatioChart profile={profile} />
        </div>
        <div className="card">
          <div className="card-title">故障模式</div>
          <FailurePatternList patterns={patterns} />
        </div>
      </div>

      {/* Section 3: Evolution Suggestions (placeholder) */}
      <div className="card">
        <div className="card-title">演化建议</div>
        <div className="text-sm text-gray-500 py-4 text-center">
          等待更多执行数据后生成演化建议
        </div>
      </div>
    </div>
  )
}
