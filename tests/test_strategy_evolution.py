"""Tests for StrategyEvolutionEngine — 基于规则的演化建议。

覆盖 5 条确定性规则 + 边界条件:
  1. 策略倾斜 (strategy > 80%)
  2. 治理阻塞 (governance_block pattern)
  3. 重试风暴 (retry_rate > 0.5)
  4. 治理率高 (governance_block_rate > 0.3)
  5. 错误多样 (error_types > 3)
"""

from __future__ import annotations

import pytest

from governance.evolution.strategy_evolution import StrategyEvolutionEngine
from governance.evolution.types import EvolutionSuggestion
from runtime.intelligence.types import (
    ExecutionAnalysisReport,
    FailurePattern,
)


class TestStrategyEvolution:
    """StrategyEvolutionEngine 测试套件。"""

    # ── Factory helpers ─────────────────────────────────────────────────

    @staticmethod
    def _make_engine() -> StrategyEvolutionEngine:
        return StrategyEvolutionEngine()

    @staticmethod
    def _make_healthy_report() -> ExecutionAnalysisReport:
        """生成一个健康报告 — 无任何问题触发规则。"""
        return ExecutionAnalysisReport(
            total_traces=100,
            success_count=95,
            failure_count=5,
            avg_duration_ms=250.0,
            p50_duration_ms=200.0,
            p95_duration_ms=500.0,
            retry_rate=0.05,
            governance_block_rate=0.02,
            strategy_distribution={"conservative": 40, "balanced": 35, "aggressive": 25},
            error_types={"timeout": 3},
            stage_durations={"plan": 100.0, "execute": 150.0},
        )

    # ── Tests ───────────────────────────────────────────────────────────

    def test_no_suggestions_on_healthy_system(self):
        """健康系统不应产生任何建议。"""
        engine = self._make_engine()
        report = self._make_healthy_report()
        suggestions = engine.suggest(report, [])

        assert suggestions == []

    def test_strategy_rebalance_suggestion(self):
        """某策略 > 80% 时触发 rebalance 建议。"""
        engine = self._make_engine()
        report = ExecutionAnalysisReport(
            total_traces=100,
            success_count=80,
            failure_count=20,
            retry_rate=0.1,
            governance_block_rate=0.0,
            strategy_distribution={
                "conservative": 90,
                "balanced": 5,
                "aggressive": 5,
            },
            error_types={"timeout": 2},
        )
        suggestions = engine.suggest(report, [])

        assert len(suggestions) == 1
        sug = suggestions[0]
        assert sug.target == "strategy"
        assert "conservative" in sug.proposed_change
        assert 0.0 < sug.confidence <= 1.0

    def test_governance_block_suggestion(self):
        """包含 governance_block 故障时触发阈值建议。"""
        engine = self._make_engine()
        report = self._make_healthy_report()
        failure_patterns = [
            FailurePattern(
                pattern_type="governance_block",
                severity=0.7,
                trace_ids=("trace_a", "trace_b"),
                description="Governance blocked execution",
            ),
        ]
        suggestions = engine.suggest(report, failure_patterns)

        assert len(suggestions) == 1
        sug = suggestions[0]
        assert sug.target == "threshold"
        assert "governance" in sug.description.lower()

    def test_multiple_suggestions(self):
        """同时满足高 retry + 高 governance_block_rate 时返回两条建议。"""
        engine = self._make_engine()
        report = ExecutionAnalysisReport(
            total_traces=100,
            success_count=60,
            failure_count=40,
            retry_rate=0.6,
            governance_block_rate=0.4,
            strategy_distribution={
                "conservative": 50,
                "balanced": 30,
                "aggressive": 20,
            },
            error_types={"timeout": 2, "permission": 1},
        )
        suggestions = engine.suggest(report, [])

        assert len(suggestions) == 2
        targets = {s.target for s in suggestions}
        assert targets == {"threshold"}  # both are threshold suggestions

        descriptions = [s.description for s in suggestions]
        assert any("retry" in d.lower() for d in descriptions)
        assert any("governance" in d.lower() for d in descriptions)

    def test_suggestion_has_evidence(self):
        """治理阻塞建议应携带相关的 trace_id 作为证据。"""
        engine = self._make_engine()
        report = self._make_healthy_report()
        failure_patterns = [
            FailurePattern(
                pattern_type="governance_block",
                severity=0.8,
                trace_ids=("trace_001", "trace_002", "trace_003"),
                description="Governance blocked execution",
            ),
        ]
        suggestions = engine.suggest(report, failure_patterns)

        assert len(suggestions) == 1
        sug = suggestions[0]
        assert len(sug.evidence) == 3
        assert "trace_001" in sug.evidence
        assert "trace_002" in sug.evidence
        assert "trace_003" in sug.evidence

    def test_all_five_rules_triggered(self):
        """所有 5 条规则同时触发。"""
        engine = self._make_engine()
        report = ExecutionAnalysisReport(
            total_traces=200,
            success_count=100,
            failure_count=100,
            retry_rate=0.8,
            governance_block_rate=0.5,
            strategy_distribution={
                "conservative": 180,  # 90% > 80%
                "balanced": 10,
                "aggressive": 10,
            },
            error_types={
                "timeout": 5,
                "permission": 3,
                "memory": 2,
                "network": 4,  # 4 types > 3
            },
        )
        failure_patterns = [
            FailurePattern(
                pattern_type="governance_block",
                severity=0.9,
                trace_ids=("trace_x",),
                description="Governance blocked",
            ),
        ]
        suggestions = engine.suggest(report, failure_patterns)

        # Expect 5 distinct suggestions
        assert len(suggestions) == 5

        # Each target should appear
        targets = [s.target for s in suggestions]
        assert targets.count("strategy") == 1
        assert targets.count("threshold") >= 2  # governance_block + retry + high_block_rate
        assert targets.count("capability") == 1

    def test_returns_empty_list_for_empty_report(self):
        """空报告应返回空列表。"""
        engine = self._make_engine()
        report = ExecutionAnalysisReport()
        suggestions = engine.suggest(report, [])

        assert suggestions == []

    def test_confidence_reflects_extremity(self):
        """置信度反映指标极端程度。"""
        engine = self._make_engine()

        # retry_rate 正好 0.5 — 不触发（需 > 0.5）
        report = ExecutionAnalysisReport(
            total_traces=100,
            success_count=50,
            failure_count=50,
            retry_rate=0.5,
            governance_block_rate=0.0,
            strategy_distribution={"conservative": 40, "balanced": 35, "aggressive": 25},
            error_types={"timeout": 2},
        )
        suggestions = engine.suggest(report, [])
        # 0.5 is at the boundary, should not trigger (strictly > 0.5)
        assert len(suggestions) == 0

        # retry_rate = 0.75 — 触发，置信度 0.75
        report2 = ExecutionAnalysisReport(
            total_traces=100,
            success_count=50,
            failure_count=50,
            retry_rate=0.75,
            governance_block_rate=0.0,
            strategy_distribution={"conservative": 40, "balanced": 35, "aggressive": 25},
            error_types={"timeout": 2},
        )
        suggestions2 = engine.suggest(report2, [])
        assert len(suggestions2) == 1
        assert suggestions2[0].confidence == pytest.approx(0.75, rel=0.01)
