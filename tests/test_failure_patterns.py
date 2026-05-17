"""Tests for FailurePatternEngine — 基于规则的故障模式检测"""

from __future__ import annotations

from runtime.intelligence.failure_patterns import FailurePatternEngine
from runtime.intelligence.types import (
    ExecutionAnalysisReport,
    FailurePatternType,
)


class TestFailurePatternEngine:
    """FailurePatternEngine 测试套件"""

    def test_no_patterns_on_healthy_system(self):
        """健康系统不触发任何模式。"""
        report = ExecutionAnalysisReport(
            total_traces=10,
            success_count=10,
            failure_count=0,
            retry_rate=0.0,
            governance_block_rate=0.0,
        )
        engine = FailurePatternEngine()
        patterns = engine.analyze(report)

        assert patterns == []

    def test_repeat_failure_detected(self):
        """REPEAT_FAILURE 正确触发。"""
        report = ExecutionAnalysisReport(
            total_traces=10,
            success_count=4,
            failure_count=6,
            retry_rate=0.6,
            governance_block_rate=0.0,
        )
        engine = FailurePatternEngine()
        patterns = engine.analyze(report)

        types_found = {p.pattern_type for p in patterns}
        assert FailurePatternType.REPEAT_FAILURE in types_found

        matched = [p for p in patterns if p.pattern_type == FailurePatternType.REPEAT_FAILURE]
        assert len(matched) == 1
        # severity = (6/10)*0.5 + 0.6*0.5 = 0.3 + 0.3 = 0.6
        assert matched[0].severity == pytest.approx(0.6, rel=0.01)

    def test_governance_block_detected(self):
        """GOVERNANCE_BLOCK 正确触发。"""
        report = ExecutionAnalysisReport(
            total_traces=10,
            success_count=5,
            failure_count=5,
            retry_rate=0.1,
            governance_block_rate=0.5,
        )
        engine = FailurePatternEngine()
        patterns = engine.analyze(report)

        types_found = {p.pattern_type for p in patterns}
        assert FailurePatternType.GOVERNANCE_BLOCK in types_found

        matched = [p for p in patterns if p.pattern_type == FailurePatternType.GOVERNANCE_BLOCK]
        assert len(matched) == 1
        assert matched[0].severity == 0.5

    def test_retry_storm_detected(self):
        """RETRY_STORM 正确触发。"""
        report = ExecutionAnalysisReport(
            total_traces=10,
            success_count=2,
            failure_count=8,
            retry_rate=0.85,
            governance_block_rate=0.1,
        )
        engine = FailurePatternEngine()
        patterns = engine.analyze(report)

        types_found = {p.pattern_type for p in patterns}
        assert FailurePatternType.RETRY_STORM in types_found

        # retry_rate > 0.7, and failure_count=8 > 3 => REPEAT_FAILURE also fires
        assert FailurePatternType.REPEAT_FAILURE in types_found

    def test_results_sorted_by_severity(self):
        """结果按 severity 降序排列。"""
        report = ExecutionAnalysisReport(
            total_traces=20,
            success_count=10,
            failure_count=10,
            retry_rate=0.9,
            governance_block_rate=0.5,
            error_types={
                "type_a": 3,
                "type_b": 2,
                "type_c": 1,
                "type_d": 1,
            },
        )
        engine = FailurePatternEngine()
        patterns = engine.analyze(report)

        assert len(patterns) >= 2
        severities = [p.severity for p in patterns]
        assert severities == sorted(severities, reverse=True)


import pytest
