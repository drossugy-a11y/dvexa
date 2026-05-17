"""RuntimeExecutionAnalyzer v1 — EventStore 执行轨迹分析器

分析 EventStore 中的执行轨迹，生成 ExecutionAnalysisReport。
只观察，不修改 runtime 状态。
"""

from __future__ import annotations

from runtime.intelligence.types import ExecutionAnalysisReport


class RuntimeExecutionAnalyzer:
    """运行执行分析器 — 从 EventStore 聚合分析执行历史。"""

    def __init__(self, event_store):
        self._event_store = event_store

    def analyze(
        self,
        trace_ids: list[str] | None = None,
        window: int = 100,
    ) -> ExecutionAnalysisReport:
        """分析执行轨迹，生成聚合报告。

        Args:
            trace_ids: 指定要分析的 trace 列表。None 表示取最近 window 条。
            window: 默认分析最近多少条 trace。

        Returns:
            不可变的 ExecutionAnalysisReport。
        """
        if trace_ids is None:
            all_traces = self._event_store.list_traces()
            trace_ids = all_traces[:window]

        if not trace_ids:
            return ExecutionAnalysisReport()

        total_traces = len(trace_ids)
        success_count = 0
        failure_count = 0
        durations: list[float] = []
        total_events_count = 0
        retry_events_count = 0
        governance_block_count = 0
        stage_durations: dict[str, float] = {}
        strategy_distribution: dict[str, int] = {}
        mode_distribution: dict[str, int] = {}
        error_types: dict[str, int] = {}

        for tid in trace_ids:
            events = self._event_store.read_by_trace(tid)
            projection = self._event_store.project(tid)

            # 成功/失败来自投影
            if projection.get("has_error"):
                failure_count += 1
            else:
                success_count += 1

            # 计算该 trace 的持续时间（从第一个事件到最后一个事件的时间戳）
            valid_timestamps = [e.timestamp for e in events if e.timestamp > 0]
            if len(valid_timestamps) >= 2:
                durations.append((max(valid_timestamps) - min(valid_timestamps)) * 1000.0)
            elif len(valid_timestamps) == 1:
                # 只有一个事件时尝试用 metadata 中的 latency
                latency_s = events[0].metadata.get("latency_s", 0)
                if latency_s:
                    durations.append(latency_s * 1000.0)

            # 逐事件分析
            for e in events:
                total_events_count += 1

                # 重试事件
                if e.event_type in ("error", "retry"):
                    retry_events_count += 1

                # 治理阻塞事件
                if e.stage == "govern" or e.event_type == "blocked":
                    governance_block_count += 1

                # 阶段耗时（从 metadata 中的 latency_s 累加）
                latency_s = e.metadata.get("latency_s", 0)
                if latency_s:
                    stage_name = e.stage
                    stage_durations[stage_name] = (
                        stage_durations.get(stage_name, 0.0) + latency_s
                    )

                # 策略分布
                strategy = e.payload.get("strategy", "")
                if strategy:
                    strategy_distribution[strategy] = (
                        strategy_distribution.get(strategy, 0) + 1
                    )

                # 模式分布
                mode = e.runtime_mode
                if mode:
                    mode_distribution[mode] = mode_distribution.get(mode, 0) + 1

                # 错误类型
                if e.event_type == "error":
                    error_detail = str(e.payload.get("error", "unknown"))
                    error_types[error_detail] = error_types.get(error_detail, 0) + 1

        # 聚合计算
        avg_duration_ms = sum(durations) / len(durations) if durations else 0.0
        retry_rate = (
            retry_events_count / total_events_count if total_events_count > 0 else 0.0
        )
        governance_block_rate = (
            governance_block_count / total_events_count
            if total_events_count > 0
            else 0.0
        )

        # 百分位
        sorted_durations = sorted(durations)
        p50 = sorted_durations[len(sorted_durations) // 2] if sorted_durations else 0.0
        p95_idx = int(len(sorted_durations) * 0.95)
        p95 = sorted_durations[p95_idx] if sorted_durations else 0.0

        return ExecutionAnalysisReport(
            total_traces=total_traces,
            success_count=success_count,
            failure_count=failure_count,
            avg_duration_ms=round(avg_duration_ms, 2),
            p50_duration_ms=round(p50, 2),
            p95_duration_ms=round(p95, 2),
            retry_rate=round(retry_rate, 4),
            governance_block_rate=round(governance_block_rate, 4),
            stage_durations={k: round(v, 4) for k, v in stage_durations.items()},
            strategy_distribution=strategy_distribution,
            mode_distribution=mode_distribution,
            error_types=error_types,
        )
