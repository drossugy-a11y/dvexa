"""Tests for Capability Governance Layer (v1.87 Resilience)"""

from governance.skill_score import (
    SkillScore, MINIMUM_SAMPLES, CONSECUTIVE_FAILURE_THRESHOLD,
    RECOVERY_SUCCESS_THRESHOLD, PRIOR_SUCCESS, PRIOR_TOTAL,
)
from governance.lifecycle import (
    SkillStatus, evaluate_lifecycle, evaluate_recovery, validate_transition,
)
from governance.conflict_detector import ConflictDetector, SkillConflict, SIMILARITY_THRESHOLD
from governance.skill_governor import SkillGovernor, _GovernedHandler, STATUS_WEIGHTS
from capabilities.skill import SkillRegistry, SkillDef
import pytest


# ─── SkillScore (v1.87 Bayesian) ─────────────────────────────────────────────

class TestSkillScore:
    def test_default_values(self):
        score = SkillScore()
        assert score.success_rate == 1.0
        assert score.consecutive_failures == 0
        assert score.recovery_attempts == 0

    def test_bayesian_rate_default(self):
        score = SkillScore()
        # (0 + 8) / (0 + 10) = 0.8
        assert score.bayesian_success_rate == pytest.approx(0.8)

    def test_bayesian_rate_after_one_success(self):
        score = SkillScore()
        score.record_success(0.1)
        # (1 + 8) / (1 + 10) = 9/11 ≈ 0.818
        assert score.bayesian_success_rate == pytest.approx(9 / 11)

    def test_bayesian_rate_single_failure_not_catastrophic(self):
        """单次失败不应让评分崩盘（v1.86 的 bug）。"""
        score = SkillScore()
        score.record_failure(0.5, "error")
        # (0 + 8) / (1 + 10) = 8/11 ≈ 0.727
        assert score.bayesian_success_rate == pytest.approx(8 / 11)
        assert score.success_rate == 0.0  # 原始 score 仍是 0，但 bayesian 平滑

    def test_combined_score_stable_after_one_failure(self):
        """贝叶斯平滑确保单次失败后 combined_score 不会崩溃。"""
        score = SkillScore()
        score.record_failure(0.5, "err")
        # 应该远高于 0（旧版 failure rate=0 时的结果）
        assert score.combined_score > 0.5

    def test_consecutive_failures_resets_on_success(self):
        score = SkillScore()
        score.record_failure(0.5)
        score.record_failure(0.5)
        assert score.consecutive_failures == 2
        score.record_success(0.1)
        assert score.consecutive_failures == 0

    def test_consecutive_failures_increments(self):
        score = SkillScore()
        for _ in range(5):
            score.record_failure(0.5)
        assert score.consecutive_failures == 5

    def test_mixed_records(self):
        score = SkillScore()
        for _ in range(9):
            score.record_success(0.1)
        score.record_failure(0.5)
        assert score.bayesian_success_rate == pytest.approx((9 + 8) / (10 + 10))


# ─── Lifecycle (v1.87) ───────────────────────────────────────────────────────

class TestLifecycle:
    def test_experimental_to_active(self):
        score = SkillScore()
        for _ in range(15):
            score.record_success(0.1)
        assert evaluate_lifecycle(SkillStatus.EXPERIMENTAL, score) == SkillStatus.ACTIVE

    def test_active_to_stable(self):
        score = SkillScore(success_rate=0.983, usage=60)
        assert evaluate_lifecycle(SkillStatus.ACTIVE, score) == SkillStatus.STABLE

    def test_active_to_degraded_on_high_error(self):
        score = SkillScore(error_rate=0.4, usage=15)
        assert evaluate_lifecycle(SkillStatus.ACTIVE, score) == SkillStatus.DEGRADED

    def test_degraded_to_quarantined(self):
        score = SkillScore(
            error_rate=0.6, usage=15,
            consecutive_failures=CONSECUTIVE_FAILURE_THRESHOLD,
        )
        assert evaluate_lifecycle(SkillStatus.DEGRADED, score) == SkillStatus.QUARANTINED

    def test_no_auto_removed(self):
        """v1.87: 即使 error_rate 极高也不自动 REMOVED。"""
        score = SkillScore(
            error_rate=0.99, usage=20,
            consecutive_failures=CONSECUTIVE_FAILURE_THRESHOLD,
        )
        assert evaluate_lifecycle(SkillStatus.ACTIVE, score) == SkillStatus.QUARANTINED
        assert evaluate_lifecycle(SkillStatus.ACTIVE, score) != SkillStatus.REMOVED

    def test_removed_is_terminal(self):
        score = SkillScore(success_rate=0.9)
        assert evaluate_lifecycle(SkillStatus.REMOVED, score) == SkillStatus.REMOVED

    def test_minimum_samples_protects_from_degraded(self):
        """usage < MINIMUM_SAMPLES 时不允许降级。"""
        score = SkillScore(error_rate=0.4, usage=MINIMUM_SAMPLES - 1)
        assert evaluate_lifecycle(SkillStatus.ACTIVE, score) == SkillStatus.ACTIVE

    def test_minimum_samples_protects_from_quarantined(self):
        score = SkillScore(
            error_rate=0.6, usage=MINIMUM_SAMPLES - 1,
            consecutive_failures=CONSECUTIVE_FAILURE_THRESHOLD,
        )
        assert evaluate_lifecycle(SkillStatus.ACTIVE, score) == SkillStatus.ACTIVE

    def test_degraded_recovery_to_active(self):
        score = SkillScore(error_rate=0.1, usage=15)
        assert evaluate_lifecycle(SkillStatus.DEGRADED, score) == SkillStatus.ACTIVE

    @pytest.mark.parametrize("status", [
        SkillStatus.ACTIVE, SkillStatus.STABLE, SkillStatus.DEGRADED,
    ])
    def test_quarantined_only_with_consecutive_failures(self, status):
        """仅 error_rate 高但无连续失败 → 不进入 QUARANTINED。"""
        score = SkillScore(error_rate=0.6, usage=15, consecutive_failures=0)
        assert evaluate_lifecycle(status, score) != SkillStatus.QUARANTINED

    def test_experimental_stays_when_below_threshold(self):
        score = SkillScore(success_rate=0.8, usage=5)
        assert evaluate_lifecycle(SkillStatus.EXPERIMENTAL, score) == SkillStatus.EXPERIMENTAL

    def test_experimental_protected_by_minimum_samples(self):
        """小样本 EXPERIMENTAL 即使高错误也不降级。"""
        score = SkillScore(error_rate=0.5, usage=3, consecutive_failures=3)
        assert evaluate_lifecycle(SkillStatus.EXPERIMENTAL, score) == SkillStatus.EXPERIMENTAL

    # ─── evaluate_recovery ─────────────────────────────────────────────

    def test_recovery_pending_with_failures(self):
        score = SkillScore(usage=10, consecutive_failures=1)
        assert evaluate_recovery(score) == "failed"

    def test_recovery_success(self):
        score = SkillScore(usage=RECOVERY_SUCCESS_THRESHOLD, consecutive_failures=0)
        assert evaluate_recovery(score) == "recovered"

    def test_recovery_pending_low_usage(self):
        score = SkillScore(usage=1, consecutive_failures=0)
        assert evaluate_recovery(score) == "pending"

    # ─── validate_transition ───────────────────────────────────────────

    def test_valid_forward_paths(self):
        assert validate_transition(SkillStatus.EXPERIMENTAL, SkillStatus.ACTIVE)
        assert validate_transition(SkillStatus.ACTIVE, SkillStatus.STABLE)
        assert validate_transition(SkillStatus.STABLE, SkillStatus.DEGRADED)
        assert validate_transition(SkillStatus.DEGRADED, SkillStatus.QUARANTINED)
        assert validate_transition(SkillStatus.QUARANTINED, SkillStatus.RECOVERED)
        assert validate_transition(SkillStatus.RECOVERED, SkillStatus.ACTIVE)

    def test_invalid_skip(self):
        assert not validate_transition(SkillStatus.EXPERIMENTAL, SkillStatus.STABLE)
        assert not validate_transition(SkillStatus.EXPERIMENTAL, SkillStatus.QUARANTINED)

    def test_deprecated_to_active_allowed(self):
        assert validate_transition(SkillStatus.DEGRADED, SkillStatus.ACTIVE)

    def test_any_to_removed_manual(self):
        """REMOVED 可人工从任何状态进入。"""
        assert validate_transition(SkillStatus.ACTIVE, SkillStatus.REMOVED)
        assert validate_transition(SkillStatus.STABLE, SkillStatus.REMOVED)
        assert validate_transition(SkillStatus.QUARANTINED, SkillStatus.REMOVED)

    def test_quarantined_back_to_active_invalid(self):
        """QUARANTINED 必须经过 RECOVERED，不能直接回 ACTIVE。"""
        assert not validate_transition(SkillStatus.QUARANTINED, SkillStatus.ACTIVE)


# ─── ConflictDetector ────────────────────────────────────────────────────────

class TestConflictDetector:
    def _make_skill(self, name, keywords):
        return SkillDef(name, lambda x: {"content": x}, keywords=keywords)

    def test_detect_overlap_above_threshold(self):
        a = self._make_skill("a", ["python", "代码", "执行", "脚本", "编译", "运行"])
        b = self._make_skill("b", ["python", "代码", "执行", "脚本", "编译", "运行", "调试"])
        cd = ConflictDetector()
        conflict = cd._check_pair(a, b)
        assert conflict is not None
        assert "python" in conflict.overlap_keywords

    def test_no_overlap(self):
        a = self._make_skill("a", ["python"])
        b = self._make_skill("b", ["java"])
        cd = ConflictDetector()
        assert cd._check_pair(a, b) is None

    def test_detect_all(self):
        a = self._make_skill("a", ["python", "代码", "执行", "脚本", "编译", "运行"])
        b = self._make_skill("b", ["python", "代码", "执行", "脚本", "编译", "运行", "调试"])
        c = self._make_skill("c", ["java"])
        cd = ConflictDetector()
        conflicts = cd.detect_all({"a": a, "b": b, "c": c})
        assert len(conflicts) == 1

    def test_similarity_threshold(self):
        assert SIMILARITY_THRESHOLD == 0.85


# ─── SkillGovernor (v1.87) ───────────────────────────────────────────────────

class TestSkillGovernor:
    def test_register(self):
        g = SkillGovernor()
        g.register("test", lambda x: {"content": x}, ["test"])
        assert g.get_score("test") is not None
        assert g.get_status("test") == SkillStatus.EXPERIMENTAL

    def test_record_call_success(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        g.record_call("t", success=True, latency=0.1)
        score = g.get_score("t")
        assert score.usage == 1
        assert score.consecutive_failures == 0

    def test_record_call_failure_tracks_consecutive(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        for _ in range(3):
            g.record_call("t", success=False, latency=1.0, error="fail")
        score = g.get_score("t")
        assert score.consecutive_failures == 3

    # ─── minimum_samples 保护 ─────────────────────────────────────────

    def test_single_failure_does_not_degrade(self):
        """v1.87 核心: 单次失败不降级。"""
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        for _ in range(5):
            g.record_call("t", success=False, latency=1.0, error="fail")
        assert g.get_status("t") == SkillStatus.EXPERIMENTAL  # 低于 minimum_samples

    def test_high_failure_still_protected_by_minimum_samples(self):
        """即使多次失败，低于 minimum_samples 也不降级。"""
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        for _ in range(MINIMUM_SAMPLES - 1):
            g.record_call("t", success=False, latency=1.0, error="fail")
        assert g.get_status("t") != SkillStatus.QUARANTINED
        assert g.get_status("t") != SkillStatus.DEGRADED

    def test_after_minimum_samples_can_degrade(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        # 先达到 minimum_samples
        for _ in range(MINIMUM_SAMPLES):
            g.record_call("t", success=True, latency=0.1)
        # 然后大量失败
        for _ in range(MINIMUM_SAMPLES):
            g.record_call("t", success=False, latency=1.0, error="fail")
        status = g.get_status("t")
        assert status in (SkillStatus.DEGRADED, SkillStatus.QUARANTINED)

    # ─── Routing 权重 ──────────────────────────────────────────────────

    def test_quarantined_weight_zero(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        g._statuses["t"] = SkillStatus.QUARANTINED
        assert g.get_routing_weight("t") == 0.0

    def test_degraded_weight_half(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        g._statuses["t"] = SkillStatus.DEGRADED
        assert g.get_routing_weight("t") == pytest.approx(0.5)

    def test_active_weight_full(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        g._statuses["t"] = SkillStatus.ACTIVE
        assert g.get_routing_weight("t") == 1.0

    def test_recovered_weight_full(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        g._statuses["t"] = SkillStatus.RECOVERED
        assert g.get_routing_weight("t") == 1.0

    # ─── best_skill_for 降级选择 ───────────────────────────────────────

    def test_degraded_still_selectable(self):
        """DEGRADED skill 仍可被选中（权重低但非 0）。"""
        g = SkillGovernor()
        g.register("only", lambda x: {"content": "ok"}, ["test"])
        g._statuses["only"] = SkillStatus.DEGRADED
        best = g.best_skill_for("test action")
        assert best is not None
        assert best.name == "only"

    def test_quarantined_not_selectable(self):
        g = SkillGovernor()
        g.register("only", lambda x: {"content": "ok"}, ["test"])
        g._statuses["only"] = SkillStatus.QUARANTINED
        assert g.best_skill_for("test action") is None

    def test_best_picks_highest_effective_score(self):
        g = SkillGovernor()
        g.register("active", lambda x: {"content": "ok"}, ["test"])
        g.register("degraded", lambda x: {"content": "ok"}, ["test"])
        g._statuses["active"] = SkillStatus.ACTIVE
        g._statuses["degraded"] = SkillStatus.DEGRADED
        for _ in range(20):
            g.record_call("active", success=True, latency=0.1)
        best = g.best_skill_for("test")
        assert best is not None
        assert best.name == "active"

    # ─── Recovery ──────────────────────────────────────────────────────

    def test_try_recovery_fails_on_non_quarantined(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        assert not g.try_recovery("t")

    def test_try_recovery_success(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        g._statuses["t"] = SkillStatus.QUARANTINED
        score = g.get_score("t")
        # 模拟恢复条件
        for _ in range(RECOVERY_SUCCESS_THRESHOLD):
            score.record_success(0.1)
        assert g.try_recovery("t")
        assert g.get_status("t") == SkillStatus.RECOVERED

    def test_try_recovery_still_failing(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x})
        g._statuses["t"] = SkillStatus.QUARANTINED
        assert not g.try_recovery("t")  # 无成功记录

    # ─── 治理指标 ──────────────────────────────────────────────────────

    def test_quarantine_count(self):
        g = SkillGovernor()
        g.register("a", lambda x: {"content": "ok"}, ["a"])
        g.register("b", lambda x: {"content": "ok"}, ["b"])
        g._statuses["a"] = SkillStatus.QUARANTINED
        assert g.quarantine_count() == 1

    def test_ecosystem_stability(self):
        g = SkillGovernor()
        g.register("a", lambda x: {"content": "ok"}, ["a"])
        g.register("b", lambda x: {"content": "ok"}, ["b"])
        g._statuses["a"] = SkillStatus.ACTIVE
        g._statuses["b"] = SkillStatus.ACTIVE
        assert g.ecosystem_stability_score() == pytest.approx(1.0)
        g._statuses["b"] = SkillStatus.QUARANTINED
        assert g.ecosystem_stability_score() < 1.0

    def test_list_all_includes_new_fields(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": "ok"}, ["test"])
        entries = g.list_all()
        assert "bayesian_success_rate" in entries[0]
        assert "consecutive_failures" in entries[0]
        assert "routing_weight" in entries[0]
        assert "recovery_attempts" in entries[0]

    # ─── wrap_handler ──────────────────────────────────────────────────

    def test_wrap_handler_records_call(self):
        g = SkillGovernor()
        handler = _SimpleHandler("ok")
        g.register("t", handler)
        wrapped = g.wrap_handler("t", handler)
        wrapped.call("input")
        assert g.get_score("t").usage == 1

    def test_wrap_handler_tracks_consecutive_failures(self):
        g = SkillGovernor()
        handler = _FailingHandler()
        g.register("t", handler)
        wrapped = g.wrap_handler("t", handler)
        for _ in range(3):
            wrapped.call("input")
        assert g.get_score("t").consecutive_failures == 3

    # ─── 边缘场景 ───────────────────────────────────────────────────────

    def test_unregister_not_supported(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": x}, ["test"])
        assert g.get_skill("t") is not None

    def test_get_status_default_for_unknown(self):
        g = SkillGovernor()
        assert g.get_status("unknown") == SkillStatus.EXPERIMENTAL

    def test_get_score_for_unknown(self):
        g = SkillGovernor()
        assert g.get_score("unknown") is None

    def test_list_by_status_experimental(self):
        g = SkillGovernor()
        g.register("a", lambda x: {"content": "ok"}, ["a"])
        result = g.list_by_status(SkillStatus.EXPERIMENTAL)
        assert len(result) == 1

    def test_list_by_status_quarantined(self):
        g = SkillGovernor()
        g.register("a", lambda x: {"content": "ok"}, ["a"])
        g._statuses["a"] = SkillStatus.QUARANTINED
        result = g.list_by_status(SkillStatus.QUARANTINED)
        assert len(result) == 1

    def test_list_by_status_empty(self):
        g = SkillGovernor()
        assert g.list_by_status(SkillStatus.QUARANTINED) == []

    def test_capability_churn_rate_zero(self):
        g = SkillGovernor()
        g.register("a", lambda x: {"content": "ok"}, ["a"])
        assert g.capability_churn_rate() == 0.0

    def test_capability_churn_rate_empty(self):
        g = SkillGovernor()
        assert g.capability_churn_rate() == 0.0

    def test_ecosystem_stability_empty(self):
        g = SkillGovernor()
        assert g.ecosystem_stability_score() == 1.0

    def test_recovery_success_rate_no_attempts(self):
        g = SkillGovernor()
        g.register("a", lambda x: {"content": "ok"}, ["a"])
        assert g.recovery_success_rate() == 1.0

    def test_recovery_success_rate_with_mixed(self):
        g = SkillGovernor()
        g.register("a", lambda x: {"content": "ok"}, ["a"])
        g.register("b", lambda x: {"content": "ok"}, ["b"])
        score_a = g.get_score("a")
        score_a.recovery_attempts = 2
        score_b = g.get_score("b")
        score_b.recovery_attempts = 1
        g._statuses["a"] = SkillStatus.RECOVERED
        assert g.recovery_success_rate() == pytest.approx(0.5)

    def test_detect_conflicts_no_skills(self):
        g = SkillGovernor()
        assert g.detect_conflicts() == []

    # ─── best_skill_for 边缘场景 ────────────────────────────────────────

    def test_best_skill_for_no_candidates(self):
        g = SkillGovernor()
        assert g.best_skill_for("nothing") is None

    def test_best_skill_for_quarantined_returns_none(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": "ok"}, ["test"])
        g._statuses["t"] = SkillStatus.QUARANTINED
        assert g.best_skill_for("test") is None

    def test_best_skill_for_removed_returns_none(self):
        g = SkillGovernor()
        g.register("t", lambda x: {"content": "ok"}, ["test"])
        g._statuses["t"] = SkillStatus.REMOVED
        assert g.best_skill_for("test") is None

    def test_best_skill_prefers_higher_weight(self):
        g = SkillGovernor()
        g.register("deg", lambda x: {"content": "ok"}, ["test"])
        g.register("act", lambda x: {"content": "ok"}, ["test"])
        g._statuses["deg"] = SkillStatus.DEGRADED
        g._statuses["act"] = SkillStatus.ACTIVE
        best = g.best_skill_for("test")
        assert best.name == "act"


    # ─── 更多 SkillScore 边缘场景 ──────────────────────────────────────

    def test_bayesian_rate_zero_usage(self):
        score = SkillScore()
        assert score.bayesian_success_rate == 8 / 10  # prior only
        assert score.bayesian_error_rate == 2 / 10

    def test_bayesian_rate_high_usage_converges(self):
        score = SkillScore()
        for _ in range(100):
            score.record_success(0.1)
        # prior 影响随 usage 增大而减小
        assert score.bayesian_success_rate == pytest.approx((100 + 8) / (100 + 10))

    def test_bayesian_error_rate_with_mixed(self):
        score = SkillScore()
        for _ in range(8):
            score.record_success(0.1)
        score.record_failure(0.5)
        assert score.bayesian_error_rate == pytest.approx((1 + 2) / (9 + 10))

    def test_combined_score_minimum_samples_healthy(self):
        score = SkillScore()
        for _ in range(MINIMUM_SAMPLES):
            score.record_success(0.1)
        assert score.combined_score > 0.8

    def test_latency_tracking(self):
        score = SkillScore()
        score.record_success(0.1)
        score.record_success(0.3)
        score.record_success(0.2)
        assert score.latency == pytest.approx(0.2)

    def test_usage_increments_correctly(self):
        score = SkillScore()
        for i in range(10):
            score.record_success(0.1)
            assert score.usage == i + 1


class TestLifecycleExtra:
    """补充生命周期测试。"""

    def test_stable_to_degraded(self):
        score = SkillScore(error_rate=0.4, usage=15)
        assert evaluate_lifecycle(SkillStatus.STABLE, score) == SkillStatus.DEGRADED

    def test_stable_to_quarantined_via_consecutive(self):
        score = SkillScore(
            error_rate=0.6, usage=15,
            consecutive_failures=CONSECUTIVE_FAILURE_THRESHOLD,
        )
        assert evaluate_lifecycle(SkillStatus.STABLE, score) == SkillStatus.QUARANTINED

    def test_recovered_to_active(self):
        score = SkillScore(success_rate=0.95, usage=15)
        assert evaluate_lifecycle(SkillStatus.RECOVERED, score) == SkillStatus.ACTIVE

    def test_recovered_stays_on_low_usage(self):
        score = SkillScore(success_rate=0.8, usage=3)
        assert evaluate_lifecycle(SkillStatus.RECOVERED, score) == SkillStatus.RECOVERED

    def test_removed_terminal_from_any_status(self):
        for status in SkillStatus:
            assert evaluate_lifecycle(SkillStatus.REMOVED, status) == SkillStatus.REMOVED

    def test_quarantined_requires_consecutive_failures(self):
        """高 error_rate 但无连续失败 → 不隔离。"""
        score = SkillScore(error_rate=0.6, usage=15, consecutive_failures=0)
        assert evaluate_lifecycle(SkillStatus.DEGRADED, score) != SkillStatus.QUARANTINED

    def test_recovery_failed_with_consecutive_failures(self):
        score = SkillScore(consecutive_failures=CONSECUTIVE_FAILURE_THRESHOLD, usage=10)
        assert evaluate_recovery(score) == "failed"

    def test_recovery_pending_low_usage_no_failures(self):
        score = SkillScore(consecutive_failures=0, usage=1)
        assert evaluate_recovery(score) == "pending"

    def test_transition_from_recovered_invalid_targets(self):
        assert not validate_transition(SkillStatus.RECOVERED, SkillStatus.QUARANTINED)
        assert not validate_transition(SkillStatus.RECOVERED, SkillStatus.STABLE)


class TestConflictDetectorExtra:
    def test_empty_keywords(self):
        a = TestConflictDetector()._make_skill("a", [])
        b = TestConflictDetector()._make_skill("b", [])
        cd = ConflictDetector()
        assert cd._check_pair(a, b) is None

    def test_single_skill_no_conflict(self):
        a = TestConflictDetector()._make_skill("a", ["python", "代码"])
        cd = ConflictDetector()
        assert cd.detect_all({"a": a}) == []

    def test_low_similarity_below_threshold(self):
        a = TestConflictDetector()._make_skill("a", ["python", "java", "rust"])
        b = TestConflictDetector()._make_skill("b", ["c++", "go", "swift"])
        cd = ConflictDetector()
        assert cd._check_pair(a, b) is None


class _SimpleHandler:
    def __init__(self, content):
        self._content = content
    def call(self, input_data):
        return {"content": self._content}


class _FailingHandler:
    def call(self, input_data):
        raise RuntimeError("simulated")
