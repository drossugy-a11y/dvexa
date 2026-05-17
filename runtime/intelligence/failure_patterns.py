"""FailurePatternEngine v1 — 基于规则的故障模式检测

纯规则引擎，不依赖 LLM。
从 ExecutionAnalysisReport 中检测故障模式。
"""

from __future__ import annotations

from runtime.intelligence.types import (
    ExecutionAnalysisReport,
    FailurePattern,
    FailurePatternType,
)


class FailurePatternEngine:
    """故障模式引擎 — 从分析报告中检测已知故障模式。"""

    def analyze(
        self,
        report: ExecutionAnalysisReport,
        event_store=None,  # 保留接口兼容性，当前版本不依赖
    ) -> list[FailurePattern]:
        """检测报告中的故障模式。

        Args:
            report: ExecutionAnalysisReport 聚合数据。
            event_store: 保留 EventStore 引用备查（当前未使用）。

        Returns:
            按 severity 降序排列的 FailurePattern 列表。
        """
        patterns: list[FailurePattern] = []

        # ── REPEAT_FAILURE ──────────────────────────────────────────────────
        # 多次失败 + 高重试率
        if report.failure_count > 3 and report.retry_rate > 0.5:
            severity = min(
                1.0,
                (report.failure_count / 10.0) * 0.5 + report.retry_rate * 0.5,
            )
            patterns.append(
                FailurePattern(
                    pattern_type=FailurePatternType.REPEAT_FAILURE,
                    severity=round(severity, 2),
                    trace_ids=(),
                    description=(
                        f"System has {report.failure_count} failures "
                        f"with {report.retry_rate:.0%} retry rate"
                    ),
                    suggestion="Check for systemic issues causing repeated failures",
                )
            )

        # ── GOVERNANCE_BLOCK ────────────────────────────────────────────────
        # 治理阻塞率过高
        if report.governance_block_rate > 0.3:
            severity = min(1.0, report.governance_block_rate)
            patterns.append(
                FailurePattern(
                    pattern_type=FailurePatternType.GOVERNANCE_BLOCK,
                    severity=round(severity, 2),
                    trace_ids=(),
                    description=(
                        f"Governance blocking "
                        f"{report.governance_block_rate:.0%} of operations"
                    ),
                    suggestion="Review governance policies for over-blocking",
                )
            )

        # ── RETRY_STORM ─────────────────────────────────────────────────────
        # 重试率极高
        if report.retry_rate > 0.7:
            severity = min(1.0, report.retry_rate)
            patterns.append(
                FailurePattern(
                    pattern_type=FailurePatternType.RETRY_STORM,
                    severity=round(severity, 2),
                    trace_ids=(),
                    description=(
                        f"Excessive retry rate at {report.retry_rate:.0%}"
                    ),
                    suggestion="Investigate root cause of retries",
                )
            )

        # ── FLAKY_PATH ──────────────────────────────────────────────────────
        # 同时存在成功和失败，说明不稳定性
        if (
            report.failure_count > 0
            and report.success_count > 0
            and report.total_traces > 5
        ):
            ratio = (
                report.failure_count / report.total_traces
                if report.total_traces > 0
                else 0
            )
            severity = min(1.0, ratio * 2.0)
            patterns.append(
                FailurePattern(
                    pattern_type=FailurePatternType.FLAKY_PATH,
                    severity=round(severity, 2),
                    trace_ids=(),
                    description=(
                        f"Mixed success/failure: {report.success_count} successes, "
                        f"{report.failure_count} failures"
                    ),
                    suggestion="Investigate intermittent failures",
                )
            )

        # ── ESCALATING_RISK ─────────────────────────────────────────────────
        # 错误类型过多，风险扩散
        if len(report.error_types) > 3:
            severity = min(1.0, len(report.error_types) / 10.0)
            patterns.append(
                FailurePattern(
                    pattern_type=FailurePatternType.ESCALATING_RISK,
                    severity=round(severity, 2),
                    trace_ids=(),
                    description=(
                        f"Multiple error types detected: "
                        f"{len(report.error_types)} distinct types"
                    ),
                    suggestion="Categorize and address each error type",
                )
            )

        # ── STALLED_RECOVERY ────────────────────────────────────────────────
        # 失败超过成功，系统未能自愈
        if (
            report.failure_count > report.success_count
            and report.total_traces > 10
        ):
            severity = min(1.0, report.failure_count / report.total_traces)
            patterns.append(
                FailurePattern(
                    pattern_type=FailurePatternType.STALLED_RECOVERY,
                    severity=round(severity, 2),
                    trace_ids=(),
                    description=(
                        f"Failures ({report.failure_count}) exceed "
                        f"successes ({report.success_count})"
                    ),
                    suggestion="Consider rolling back recent changes or escalating",
                )
            )

        # 按 severity 降序排列
        patterns.sort(key=lambda p: p.severity, reverse=True)
        return patterns
