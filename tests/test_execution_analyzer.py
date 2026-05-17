"""Tests for RuntimeExecutionAnalyzer — EventStore 执行轨迹分析器"""

from __future__ import annotations

from unittest.mock import MagicMock

from runtime.event import Event
from runtime.intelligence.execution_analyzer import RuntimeExecutionAnalyzer


class TestRuntimeExecutionAnalyzer:
    """RuntimeExecutionAnalyzer 测试套件"""

    def _make_mock_store(
        self, traces: dict[str, tuple[list[Event], dict]]
    ) -> MagicMock:
        """创建模拟 EventStore。

        Args:
            traces: trace_id → (events_list, projection_dict) 映射。

        Returns:
            配置好的 MagicMock EventStore。
        """
        store = MagicMock()
        store.list_traces.return_value = sorted(traces.keys())

        def read_by_trace(tid: str) -> list[Event]:
            data = traces.get(tid)
            return list(data[0]) if data else []

        def project(tid: str) -> dict:
            data = traces.get(tid)
            return dict(data[1]) if data else {}

        store.read_by_trace.side_effect = read_by_trace
        store.project.side_effect = project
        return store

    def test_empty_store(self):
        """空 EventStore 返回全零报告。"""
        store = MagicMock()
        store.list_traces.return_value = []

        analyzer = RuntimeExecutionAnalyzer(store)
        report = analyzer.analyze()

        assert report.total_traces == 0
        assert report.success_count == 0
        assert report.failure_count == 0
        assert report.avg_duration_ms == 0.0
        assert report.retry_rate == 0.0
        assert report.governance_block_rate == 0.0
        assert report.stage_durations == {}
        assert report.strategy_distribution == {}
        assert report.mode_distribution == {}
        assert report.error_types == {}

    def test_single_trace(self):
        """单条成功 trace 返回正确计数。"""
        tid = "trc-001"
        events = [
            Event(
                trace_id=tid,
                stage="load",
                event_type="info",
                payload={"strategy": "default"},
                timestamp=1000.0,
                metadata={"latency_s": 0.1},
                runtime_mode="task",
            ),
            Event(
                trace_id=tid,
                stage="log",
                event_type="info",
                payload={},
                timestamp=1002.5,
                metadata={"latency_s": 0.05},
                runtime_mode="task",
            ),
        ]
        projection = {
            "has_error": False,
            "total_events": 2,
            "stages": ["load", "log"],
        }
        store = self._make_mock_store({tid: (events, projection)})

        analyzer = RuntimeExecutionAnalyzer(store)
        report = analyzer.analyze()

        assert report.total_traces == 1
        assert report.success_count == 1
        assert report.failure_count == 0
        # 2.5s = 2500ms
        assert report.avg_duration_ms == 2500.0
        assert report.stage_durations["load"] == 0.1
        assert report.stage_durations["log"] == 0.05
        assert report.strategy_distribution == {"default": 1}
        assert report.mode_distribution == {"task": 2}
        assert report.error_types == {}

    def test_multiple_traces(self):
        """多条 trace 正确聚合。"""
        traces = {}
        for i in range(3):
            tid = f"trc-{i:03d}"
            has_err = i == 2  # 第三条 trace 失败
            # 第三条约 3 秒，前两条约 1 秒
            dur = 3.0 if has_err else 1.0
            events = [
                Event(
                    trace_id=tid,
                    stage="load",
                    event_type="info",
                    payload={"strategy": "default"},
                    timestamp=1000.0,
                    metadata={"latency_s": 0.1},
                    runtime_mode="task",
                ),
                Event(
                    trace_id=tid,
                    stage="govern" if has_err else "log",
                    event_type="risk" if has_err else "info",
                    payload={"error": "policy_denied"} if has_err else {},
                    timestamp=1000.0 + dur,
                    metadata={"latency_s": 0.05},
                    runtime_mode="task",
                ),
            ]
            projection = {"has_error": has_err, "total_events": len(events)}
            traces[tid] = (events, projection)

        store = self._make_mock_store(traces)
        analyzer = RuntimeExecutionAnalyzer(store)
        report = analyzer.analyze()

        assert report.total_traces == 3
        assert report.success_count == 2
        assert report.failure_count == 1
        # 平均 duration: (1 + 1 + 3) * 1000 / 3 ≈ 1666.67
        assert report.avg_duration_ms == pytest.approx(1666.67, rel=0.01)
        # 有一条 risk 事件 => governance_block_count=1, total_events=6
        assert report.governance_block_rate == pytest.approx(1 / 6, rel=0.01)

    def test_retry_detection(self):
        """正确检测重试事件。"""
        tid = "trc-retry"
        events = [
            Event(
                trace_id=tid,
                stage="schedule",
                event_type="info",
                payload={},
                timestamp=1000.0,
            ),
            Event(
                trace_id=tid,
                stage="execution",
                event_type="error",
                payload={"error": "timeout"},
                timestamp=1001.0,
            ),
            Event(
                trace_id=tid,
                stage="execution",
                event_type="retry",
                payload={"attempt": 2},
                timestamp=1001.5,
            ),
            Event(
                trace_id=tid,
                stage="execution",
                event_type="info",
                payload={},
                timestamp=1003.0,
            ),
            Event(
                trace_id=tid,
                stage="log",
                event_type="info",
                payload={},
                timestamp=1004.0,
            ),
        ]
        projection = {"has_error": True, "total_events": 5}
        store = self._make_mock_store({tid: (events, projection)})

        analyzer = RuntimeExecutionAnalyzer(store)
        report = analyzer.analyze()

        assert report.failure_count == 1
        # 5 个事件中，2 个是 retry/error => 2/5 = 0.4
        assert report.retry_rate == pytest.approx(0.4, rel=0.01)
        assert report.error_types.get("timeout") == 1

    def test_window_parameter(self):
        """window 参数限制分析范围。"""
        traces: dict = {}
        for i in range(10):
            tid = f"trc-{i:03d}"
            events = [
                Event(
                    trace_id=tid,
                    stage="load",
                    event_type="info",
                    payload={},
                    timestamp=float(i),
                ),
            ]
            projection = {"has_error": False}
            traces[tid] = (events, projection)

        store = MagicMock()
        store.list_traces.return_value = sorted(traces.keys())

        # 控制 read_by_trace 和 project 只返回前 window 个
        call_count = [0]

        def read_by_trace(tid: str) -> list[Event]:
            call_count[0] += 1
            data = traces.get(tid)
            return list(data[0]) if data else []

        def project(tid: str) -> dict:
            data = traces.get(tid)
            return dict(data[1]) if data else {}

        store.read_by_trace.side_effect = read_by_trace
        store.project.side_effect = project

        analyzer = RuntimeExecutionAnalyzer(store)
        report = analyzer.analyze(window=3)

        assert report.total_traces == 3
        # 只处理了 3 条 trace
        assert call_count[0] == 3


import pytest
