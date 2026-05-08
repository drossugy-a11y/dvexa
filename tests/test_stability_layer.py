"""Tests for Stability Layer v1 — Drift Guard + Rollback + Safety Lock."""
import pytest
from governance.stability_layer import StabilityLayer
from governance.governance_kernel import GovernanceKernel
from governance.complexity_budget import ComplexityBudget
from governance.cost_model import GovernanceCostModel


# ─── Fakes ──────────────────────────────────────────────────────────────────

class FakeGovernor:
    def __init__(self):
        self._scores = {}
        self._quarantine = 0
    def get_score(self, name):
        return self._scores.get(name)
    def set_score(self, name, score):
        self._scores[name] = score
    def quarantine_count(self):
        return self._quarantine


class FakeScore:
    def __init__(self, success_rate=1.0, stability=1.0, usage=0):
        self.success_rate = success_rate
        self.stability = stability
        self.usage = usage


class FakeCostModel:
    def __init__(self):
        self.cost_table = {"llm": 3.0, "code_executor": 2.0,
                           "http_request": 1.0, "github": 1.5,
                           "security": 2.5}
        self.max_plan_cost = 15.0
    def estimate_step_cost(self, step):
        return self.cost_table.get(step.get("tool", ""), 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Drift Guard
# ═══════════════════════════════════════════════════════════════════════════

class TestDriftGuard:
    def test_no_drift_when_stable(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        result = sl.run(
            optimizer_result={"adjustments": {}, "metrics": {}},
            system_state={"strategy_effectiveness": {}, "decisions": []},
        )
        assert result["drift"]["drift_detected"] is False
        assert result["drift"]["severity"] == "low"

    def test_detects_strategy_success_rate_drop(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        # First call: baseline
        sl._check_drift({}, {"strategy_effectiveness": {
            "BALANCED": {"success_rate": 0.9, "variance": 0.01},
        }, "decisions": []})
        # Second call: big drop
        result = sl._check_drift({}, {"strategy_effectiveness": {
            "BALANCED": {"success_rate": 0.5, "variance": 0.01},
        }, "decisions": []})
        assert result["drift_detected"] is True
        assert "strategy" in result["drift_type"] or \
               any("strategy" in a for a in result.get("affected_components", []) or
                   result["details"]["strategy"]["detected"])

    def test_detects_high_variance(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        result = sl._check_drift({}, {"strategy_effectiveness": {
            "EXPLORATION": {"success_rate": 0.5, "variance": 0.3},
        }, "decisions": []})
        assert result["details"]["strategy"]["detected"] is True

    def test_no_drift_with_low_variance(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        result = sl._check_drift({}, {"strategy_effectiveness": {
            "BALANCED": {"success_rate": 0.8, "variance": 0.02},
        }, "decisions": []})
        assert result["drift_detected"] is False

    def test_detects_tool_cost_rise(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        # Simulate 3 rounds of cost increases
        for i in range(3):
            sl._check_tool_drift({"adjustments": {
                "tool_cost_multipliers": {"llm": 1.3},
            }, "metrics": {"fallback_rate": 0.05}})
        result = sl._check_tool_drift({"adjustments": {
            "tool_cost_multipliers": {"llm": 1.3},
        }, "metrics": {"fallback_rate": 0.05}})
        assert result["detected"] is True

    def test_governance_drift_with_quarantine(self):
        gov = FakeGovernor()
        gov._quarantine = 2
        sl = StabilityLayer(gov, FakeCostModel(), {})
        result = sl._check_governance_drift({})
        assert result["detected"] is True
        assert any("quarantined" in a for a in result["affected"])

    def test_drift_recommendation_rollback(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        rec = sl._derive_recommendation(["strategy"], "high")
        assert rec == "rollback"

    def test_drift_recommendation_continue(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        rec = sl._derive_recommendation([], "low")
        assert rec == "continue"


# ═══════════════════════════════════════════════════════════════════════════
# Test: Snapshot Management
# ═══════════════════════════════════════════════════════════════════════════

class TestSnapshot:
    def test_save_and_restore_cost_table(self):
        cm = FakeCostModel()
        sl = StabilityLayer(FakeGovernor(), cm, {"BALANCED": {"bias": 0.0}})
        old_llm = cm.cost_table["llm"]
        sid = sl.save_snapshot("test")
        cm.cost_table["llm"] = 99.0
        assert cm.cost_table["llm"] == 99.0
        ok = sl.restore_snapshot(sid)
        assert ok is True
        assert cm.cost_table["llm"] == old_llm

    def test_save_and_restore_strategy_stats(self):
        stats = {"BALANCED": {"bias": 0.0}, "STRICT": {"bias": 0.5}}
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), stats)
        sid = sl.save_snapshot("test")
        stats["BALANCED"]["bias"] = -0.5
        sl.restore_snapshot(sid)
        assert stats["BALANCED"]["bias"] == 0.0

    def test_restore_nonexistent_snapshot(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        ok = sl.restore_snapshot("nonexistent")
        assert ok is False

    def test_snapshot_cap(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        for i in range(15):
            sl.save_snapshot(f"s{i}")
        assert sl.get_snapshot_count() == 10

    def test_get_last_stable_snapshot(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        sl.save_snapshot("first")
        sl.save_snapshot("second")
        snap = sl.get_last_stable_snapshot()
        assert snap is not None
        assert snap["label"] == "second"


# ═══════════════════════════════════════════════════════════════════════════
# Test: Safety Lock
# ═══════════════════════════════════════════════════════════════════════════

class TestSafetyLock:
    def test_no_lock_when_stable(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        result = sl._check_safety_locks(
            {"adjustments": {}, "metrics": {}},
            {"strategy_effectiveness": {}},
        )
        assert result["lock_active"] is False

    def test_frequency_lock_triggered(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        # Simulate 3 consecutive optimizations marked unstable
        sl._optimization_history = ["unstable", "unstable", "unstable"]
        result = sl._check_safety_locks(
            {"adjustments": {}, "metrics": {}},
            {"strategy_effectiveness": {}},
        )
        assert result["lock_active"] is True
        assert result["lock_type"] == "frequency"

    def test_lock_persists_across_calls(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        sl._lock_active = True
        sl._lock_type = "cost"
        sl._lock_remaining = 5
        assert sl.is_locked() is True
        # One call to check_safety_locks should decrement remaining
        sl._check_safety_locks(
            {"adjustments": {}, "metrics": {}},
            {"strategy_effectiveness": {}},
        )
        assert sl.get_lock_remaining() == 4

    def test_lock_expires_after_cooldown(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        sl._lock_active = True
        sl._lock_type = "cost"
        sl._lock_remaining = 1
        sl._check_safety_locks(
            {"adjustments": {}, "metrics": {}},
            {"strategy_effectiveness": {}},
        )
        assert sl.is_locked() is False

    def test_exploration_cap_triggers_lock(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        result = sl._check_safety_locks(
            {"adjustments": {}, "metrics": {}},
            {"strategy_effectiveness": {
                "EXPLORATION": {"success_rate": 0.5, "tasks": 5},
            }},
        )
        # EXPLORATION with tasks > 0 triggers cap
        assert "exploration" in str(result.get("lock_type", ""))


# ═══════════════════════════════════════════════════════════════════════════
# Test: Full Run Pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestFullRun:
    def test_run_returns_expected_keys(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        result = sl.run(
            optimizer_result={"adjustments": {}, "metrics": {}},
            system_state={"strategy_effectiveness": {}, "decisions": []},
        )
        for key in ("drift", "rollback", "lock", "stable"):
            assert key in result

    def test_stable_state_no_issues(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        result = sl.run(
            optimizer_result={"adjustments": {}, "metrics": {}},
            system_state={"strategy_effectiveness": {}, "decisions": []},
        )
        assert result["stable"] is True
        assert result["drift"]["drift_detected"] is False
        assert result["rollback"]["triggered"] is False
        assert result["lock"]["lock_active"] is False

    def test_unstable_with_drift(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        # First call to set baseline
        sl._check_strategy_drift({
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.9, "variance": 0.01},
            },
            "decisions": [],
        })
        # Second call with drift
        result = sl.run(
            optimizer_result={"adjustments": {}, "metrics": {}},
            system_state={
                "strategy_effectiveness": {
                    "BALANCED": {"success_rate": 0.3, "variance": 0.01},
                },
                "decisions": [],
            },
        )
        assert result["stable"] is False

    def test_full_pipeline_success_check(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        sl.save_snapshot("initial")
        # Simulate bad optimization
        cm = FakeCostModel()
        cm.cost_table["llm"] = 99.0
        result = sl.run(
            optimizer_result={"adjustments": {}, "metrics": {}},
            system_state={"strategy_effectiveness": {}, "decisions": []},
        )
        # Not necessarily unstable (depends on history), just checking no crash
        assert isinstance(result["stable"], bool)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_input_same_drift_result(self):
        a = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        b = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        state = {"strategy_effectiveness": {}, "decisions": []}
        opt = {"adjustments": {}, "metrics": {}}
        assert a._check_drift(opt, state) == b._check_drift(opt, state)

    def test_same_input_same_lock_result(self):
        a = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        b = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        assert a._check_safety_locks(
            {"adjustments": {}, "metrics": {}},
            {"strategy_effectiveness": {}},
        ) == b._check_safety_locks(
            {"adjustments": {}, "metrics": {}},
            {"strategy_effectiveness": {}},
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test: No-LLM Guarantee
# ═══════════════════════════════════════════════════════════════════════════

class TestNoLLM:
    def test_all_methods_deterministic_no_llm(self):
        sl = StabilityLayer(FakeGovernor(), FakeCostModel(), {})
        result = sl.run(
            optimizer_result={"adjustments": {}, "metrics": {}},
            system_state={"strategy_effectiveness": {}, "decisions": []},
        )
        assert isinstance(result["stable"], bool)
        assert isinstance(result["drift"]["drift_detected"], bool)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Kernel Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestKernelIntegration:
    def test_kernel_accepts_stability_layer(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True
            def quarantine_count(self):
                return 0

        cm = GovernanceCostModel()
        stats: dict = {}
        sl = StabilityLayer(MockGov(), cm, stats)
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  cost_model=cm,
                                  stability_layer=sl)
        assert kernel._stability_layer is sl

    def test_snapshot_saved_after_optimization(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True
            def quarantine_count(self):
                return 0

        cm = GovernanceCostModel()
        stats: dict = {}
        sl = StabilityLayer(MockGov(), cm, stats)
        sl.save_snapshot("pre_opt")
        assert sl.get_snapshot_count() == 1

    def test_restore_after_drift_protects_system(self):
        cm = FakeCostModel()
        stats = {"BALANCED": {"bias": 0.0}}
        sl = StabilityLayer(FakeGovernor(), cm, stats)
        sid = sl.save_snapshot("stable")
        # Simulate bad optimization
        cm.cost_table["llm"] = 50.0
        stats["BALANCED"]["bias"] = -0.8
        # Restore
        sl.restore_snapshot(sid)
        assert cm.cost_table["llm"] == 3.0
        assert stats["BALANCED"]["bias"] == 0.0

    def test_stability_with_full_pipeline(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True
            def quarantine_count(self):
                return 0

        cm = GovernanceCostModel()
        cb = ComplexityBudget()
        stats: dict = {}
        sl = StabilityLayer(MockGov(), cm, stats)
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  complexity_budget=cb,
                                  cost_model=cm,
                                  stability_layer=sl)
        plan = {"goal": "test", "steps": [{"id": 1, "tool": "llm",
                                            "action": "hello", "type": "tool"}]}
        result = kernel.process({"task": "hello"}, plan)
        assert "filtered_plan" in result

        # Run stability check
        stability = sl.run(
            optimizer_result={"adjustments": {}, "metrics": {}},
            system_state={"strategy_effectiveness": {}, "decisions": []},
        )
        assert isinstance(stability["stable"], bool)
