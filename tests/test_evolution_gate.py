"""Tests for EvolutionGate — 演化闸门四道检查。

覆盖场景:
  - 健康 MCP + SL → 全通过
  - 健康得分低 → 阻塞
  - 漂移检测 → 阻塞
  - 无 MCP / 无 SL → 优雅降级
  - 多条建议各自获得独立的判定
  - summary 正确反映 PASS / BLOCKED
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from governance.evolution.evolution_gate import EvolutionGate
from governance.evolution.types import (
    EvolutionSuggestion,
    EvolutionVerdict,
    GateCheckResult,
)


class TestEvolutionGate:
    """EvolutionGate 测试套件。"""

    # ── Factory helpers ─────────────────────────────────────────────────

    @staticmethod
    def _make_suggestion(
        target: str = "threshold",
        description: str = "test suggestion",
    ) -> EvolutionSuggestion:
        return EvolutionSuggestion(
            target=target,
            proposed_change="test change",
            confidence=0.8,
            evidence=(),
            description=description,
        )

    @staticmethod
    def _mock_mcp(health: float = 1.0) -> MagicMock:
        """创建模拟 MetaControlPlane。"""
        mcp = MagicMock()
        mcp.system_health_monitor.health_score = health
        return mcp

    @staticmethod
    def _mock_sl(
        drift: bool = False,
        rollback: bool = False,
        locked: bool = False,
    ) -> MagicMock:
        """创建模拟 StabilityLayer。"""
        sl = MagicMock()
        sl.drift_detected = drift
        sl.rollback = {"triggered": rollback, "reasons": []}

        if locked:
            sl.is_locked.return_value = True
        else:
            sl.is_locked.return_value = False

        return sl

    @staticmethod
    def _count_check_results(
        verdict: EvolutionVerdict, check_name: str,
    ) -> int:
        """统计 verdict 中指定检查名称的出现次数。"""
        count = 0
        for c in verdict.passed_checks:
            if c.check_name == check_name:
                count += 1
        for c in verdict.failed_checks:
            if c.check_name == check_name:
                count += 1
        return count

    # ── Tests ───────────────────────────────────────────────────────────

    def test_all_checks_pass(self):
        """健康 MCP + SL → 所有检查通过。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=1.0),
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        suggestion = self._make_suggestion()
        verdicts = gate.check([suggestion])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is True
        assert verdicts[0].summary == "PASS"
        assert len(verdicts[0].failed_checks) == 0

    def test_health_below_threshold(self):
        """低健康得分 → 健康检查失败。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=0.3),
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is False
        # At least health should be in failed_checks
        failed_names = [c.check_name for c in verdicts[0].failed_checks]
        assert "health" in failed_names

    def test_drift_detected(self):
        """漂移检测 → 漂移检查失败。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=1.0),
            stability_layer=self._mock_sl(drift=True, rollback=False),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is False
        failed_names = [c.check_name for c in verdicts[0].failed_checks]
        assert "drift" in failed_names

    def test_no_meta_control_plane(self):
        """无 MetaControlPlane → 健康检查跳过（通过）。"""
        gate = EvolutionGate(
            meta_control_plane=None,
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is True
        assert verdicts[0].summary == "PASS"

    def test_no_stability_layer(self):
        """无 StabilityLayer → 漂移/回滚检查跳过（通过）。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=1.0),
            stability_layer=None,
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is True
        assert verdicts[0].summary == "PASS"

    def test_no_mcp_nor_sl(self):
        """MCP 和 SL 均缺失 → 所有非必选检查跳过，全部通过。"""
        gate = EvolutionGate(
            meta_control_plane=None,
            stability_layer=None,
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is True
        # All 4 checks should be in passed_checks
        passed_names = [c.check_name for c in verdicts[0].passed_checks]
        assert "health" in passed_names
        assert "drift" in passed_names
        assert "rollback" in passed_names
        assert "benchmark" in passed_names

    def test_multiple_suggestions(self):
        """多条建议 → 每条获得独立的 EvolutionVerdict。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=1.0),
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        suggestions = [
            self._make_suggestion(target="strategy", description="sug 1"),
            self._make_suggestion(target="threshold", description="sug 2"),
            self._make_suggestion(target="capability", description="sug 3"),
        ]
        verdicts = gate.check(suggestions)

        assert len(verdicts) == 3
        for v in verdicts:
            assert v.allowed is True
            assert v.summary == "PASS"

        # Each should have a unique suggestion_id
        ids = [v.suggestion_id for v in verdicts]
        assert len(set(ids)) == 3

    def test_verdict_summary_blocked(self):
        """被阻塞的 verdict → summary 包含 'BLOCKED'。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=0.1),
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is False
        assert "BLOCKED" in verdicts[0].summary
        assert "health" in verdicts[0].summary

    def test_verdict_summary_pass(self):
        """通过的 verdict → summary 为 'PASS'。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=1.0),
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is True
        assert verdicts[0].summary == "PASS"

    def test_rollback_active(self):
        """回滚激活 → 回滚检查失败。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=1.0),
            stability_layer=self._mock_sl(drift=False, rollback=True),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is False
        failed_names = [c.check_name for c in verdicts[0].failed_checks]
        assert "rollback" in failed_names

    def test_all_checks_are_run_for_each_suggestion(self):
        """每条建议都经过 4 项检查。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=1.0),
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        suggestions = [
            self._make_suggestion(description="sug a"),
            self._make_suggestion(description="sug b"),
        ]
        verdicts = gate.check(suggestions)

        for v in verdicts:
            total_checks = len(v.passed_checks) + len(v.failed_checks)
            assert total_checks == 4

    def test_health_at_boundary_passes(self):
        """健康得分正好 0.6 → 通过（>= 阈值）。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=0.6),
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        # health check should pass (0.6 >= 0.6)
        passed_names = [c.check_name for c in verdicts[0].passed_checks]
        assert "health" in passed_names

    def test_health_just_below_boundary_fails(self):
        """健康得分 0.599 → 不通过（< 阈值）。"""
        gate = EvolutionGate(
            meta_control_plane=self._mock_mcp(health=0.599),
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        failed_names = [c.check_name for c in verdicts[0].failed_checks]
        assert "health" in failed_names

    def test_mcp_process_fallback(self):
        """MCP 无 health_score 属性时回退调用 process()。"""
        mcp = MagicMock()
        # 不设置 system_health_monitor.health_score → 触发回退
        mcp.process.return_value = {
            "meta_decision": {"health_score": 0.9},
        }
        gate = EvolutionGate(
            meta_control_plane=mcp,
            stability_layer=self._mock_sl(drift=False, rollback=False),
        )
        verdicts = gate.check([self._make_suggestion()])

        assert len(verdicts) == 1
        assert verdicts[0].allowed is True
        mcp.process.assert_called_once()
