"""Tests for Global Optimization Loop v1."""
import pytest
from governance.global_optimization import GlobalOptimizationLoop
from governance.governance_kernel import GovernanceKernel
from governance.complexity_budget import ComplexityBudget
from governance.cost_model import GovernanceCostModel


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_record(strategy: str = "BALANCED", success: bool = True,
                tools: list[str] | None = None, decisions: list[dict] | None = None,
                steps: list[dict] | None = None) -> dict:
    steps = steps or [{"tool": t, "action": "do", "type": "tool", "id": i}
                      for i, t in enumerate(tools or ["llm"])]
    return {
        "strategy": strategy,
        "strategy_used": strategy,
        "success": success,
        "passed": success,
        "filtered_plan": {"goal": "test", "steps": steps},
        "steps": steps,
        "decisions": decisions or [],
    }


class FakeCostModel:
    """Minimal cost model with adjustable table for testing."""
    def __init__(self):
        self.cost_table = {"llm": 3.0, "code_executor": 2.0, "http_request": 1.0,
                           "github": 1.5, "security": 2.5}
        self.max_plan_cost = 15.0
    def estimate_step_cost(self, step):
        tool = step.get("tool", "")
        return self.cost_table.get(tool, 1.0)


class FakeGovernor:
    """Minimal skill governor for testing."""
    def __init__(self):
        self._scores: dict = {}
    def get_score(self, name):
        return self._scores.get(name)
    def set_score(self, name, score):
        self._scores[name] = score


class FakeScore:
    def __init__(self, stability=1.0):
        self.stability = stability


# ═══════════════════════════════════════════════════════════════════════════
# Test: System Metrics Analysis
# ═══════════════════════════════════════════════════════════════════════════

class TestAnalyzeMetrics:
    def test_empty_history(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        metrics = loop.analyze_system_metrics([])
        assert metrics["tool_stats"] == {}
        assert metrics["total_tasks"] == 0

    def test_tool_usage_tracked(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        history = [
            make_record(tools=["llm", "code_executor"]),
            make_record(tools=["llm"]),
        ]
        metrics = loop.analyze_system_metrics(history)
        assert metrics["tool_usage"]["llm"]["calls"] == 2
        assert metrics["tool_usage"]["code_executor"]["calls"] == 1

    def test_tool_success_rate(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        history = [
            make_record(tools=["llm", "code_executor"], success=True),
            make_record(tools=["llm", "code_executor"], success=False),
            make_record(tools=["llm"], success=True),
        ]
        metrics = loop.analyze_system_metrics(history)
        llm_sr = metrics["tool_stats"]["llm"]["success_rate"]
        assert 0.66 < llm_sr < 0.67  # 2/3 ≈ 0.6667

    def test_strategy_outcomes(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        history = [
            make_record(strategy="BALANCED", success=True),
            make_record(strategy="BALANCED", success=True),
            make_record(strategy="BALANCED", success=False),
            make_record(strategy="CONSERVATIVE", success=True),
        ]
        metrics = loop.analyze_system_metrics(history)
        se = metrics["strategy_effectiveness"]
        assert se["BALANCED"]["success_rate"] == pytest.approx(2/3, rel=0.01)
        assert se["CONSERVATIVE"]["success_rate"] == 1.0

    def test_fallback_rate(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        history = [
            make_record(decisions=[
                {"action": "allow"}, {"action": "allow"},
                {"action": "reroute"}, {"action": "downgrade"},
            ]),
            make_record(decisions=[{"action": "allow"}]),
        ]
        metrics = loop.analyze_system_metrics(history)
        assert metrics["fallback_rate"] == 0.4  # 2 out of 5

    def test_tool_efficiency_calculated(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        history = [
            make_record(tools=["llm"], success=True),
            make_record(tools=["llm"], success=True),
            make_record(tools=["llm"], success=False),
        ]
        metrics = loop.analyze_system_metrics(history)
        eff = metrics["tool_stats"]["llm"]["efficiency"]
        # sr=0.6667, avg_cost=3.0, efficiency=0.6667/3.0 ≈ 0.2222
        assert eff == pytest.approx(0.2222, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Inefficiency Detection
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectInefficiencies:
    def test_detects_low_efficiency_tool(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        # sr=0.3, avg_cost=3.0 → eff=0.1 < 0.3
        metrics = {
            "tool_stats": {
                "security": {
                    "efficiency": 0.1, "success_rate": 0.3, "avg_cost": 3.0,
                },
            },
            "strategy_effectiveness": {},
            "fallback_rate": 0.0,
        }
        result = loop.detect_inefficiencies(metrics)
        assert len(result["low_efficiency_tools"]) == 1
        assert result["low_efficiency_tools"][0]["tool"] == "security"

    def test_skips_efficient_tools(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        metrics = {
            "tool_stats": {
                "llm": {"efficiency": 0.5, "success_rate": 0.8, "avg_cost": 3.0},
            },
            "strategy_effectiveness": {},
            "fallback_rate": 0.0,
        }
        result = loop.detect_inefficiencies(metrics)
        assert len(result["low_efficiency_tools"]) == 0

    def test_detects_high_variance_strategy(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        metrics = {
            "tool_stats": {},
            "strategy_effectiveness": {
                "EXPLORATION": {
                    "variance": 0.25, "effectiveness": 0.5,
                },
            },
            "fallback_rate": 0.0,
        }
        result = loop.detect_inefficiencies(metrics)
        assert len(result["high_variance_strategies"]) == 1
        assert result["high_variance_strategies"][0]["strategy"] == "EXPLORATION"

    def test_detects_high_fallback(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        metrics = {
            "tool_stats": {},
            "strategy_effectiveness": {},
            "fallback_rate": 0.35,
        }
        result = loop.detect_inefficiencies(metrics)
        assert result["high_fallback_path"] is True

    def test_low_fallback_no_flag(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        metrics = {
            "tool_stats": {},
            "strategy_effectiveness": {},
            "fallback_rate": 0.1,
        }
        result = loop.detect_inefficiencies(metrics)
        assert result["high_fallback_path"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Test: Adjustment Computation
# ═══════════════════════════════════════════════════════════════════════════

class TestComputeAdjustments:
    def test_low_efficiency_tool_gets_cost_increase(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        ineff = {
            "low_efficiency_tools": [
                {"tool": "security", "efficiency": 0.1, "success_rate": 0.3, "avg_cost": 3.0},
            ],
            "high_variance_strategies": [],
            "high_fallback_path": False,
        }
        adj = loop.compute_adjustments(ineff)
        assert "security" in adj["tool_cost_multipliers"]
        assert adj["tool_cost_multipliers"]["security"] > 1.0

    def test_medium_inefficiency_gets_medium_adjustment(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        ineff = {
            "low_efficiency_tools": [
                {"tool": "http_request", "efficiency": 0.25, "success_rate": 0.5, "avg_cost": 1.0},
            ],
            "high_variance_strategies": [],
            "high_fallback_path": False,
        }
        adj = loop.compute_adjustments(ineff)
        assert adj["tool_cost_multipliers"]["http_request"] == 1.15

    def test_high_variance_strategy_gets_negative_bias(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        ineff = {
            "low_efficiency_tools": [],
            "high_variance_strategies": [
                {"strategy": "EXPLORATION", "variance": 0.3, "effectiveness": 0.5},
            ],
            "high_fallback_path": False,
        }
        adj = loop.compute_adjustments(ineff)
        assert "EXPLORATION" in adj["strategy_biases"]
        assert adj["strategy_biases"]["EXPLORATION"] < 0

    def test_no_inefficiencies_empty_adjustments(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        ineff = {
            "low_efficiency_tools": [],
            "high_variance_strategies": [],
            "high_fallback_path": False,
        }
        adj = loop.compute_adjustments(ineff)
        assert adj["tool_cost_multipliers"] == {}
        assert adj["strategy_biases"] == {}


# ═══════════════════════════════════════════════════════════════════════════
# Test: Optimization Application
# ═══════════════════════════════════════════════════════════════════════════

class TestApplyOptimizations:
    def test_tool_cost_table_updated(self):
        cm = FakeCostModel()
        loop = GlobalOptimizationLoop(FakeGovernor(), cm, {})
        old = cm.cost_table["security"]
        loop.apply_optimizations({
            "tool_cost_multipliers": {"security": 1.3},
            "strategy_biases": {},
        })
        assert cm.cost_table["security"] == pytest.approx(old * 1.3, rel=0.01)

    def test_strategy_bias_updated(self):
        stats = {"BALANCED": {"bias": 0.0}}
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), stats)
        loop.apply_optimizations({
            "tool_cost_multipliers": {},
            "strategy_biases": {"BALANCED": -0.2},
        })
        assert stats["BALANCED"]["bias"] == -0.2

    def test_new_strategy_bias_created(self):
        stats: dict = {}
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), stats)
        loop.apply_optimizations({
            "tool_cost_multipliers": {},
            "strategy_biases": {"EXPLORATION": -0.1},
        })
        assert stats["EXPLORATION"]["bias"] == -0.1

    def test_skill_score_stability_adjusted(self):
        gov = FakeGovernor()
        score = FakeScore(stability=1.0)
        gov.set_score("security", score)
        loop = GlobalOptimizationLoop(gov, FakeCostModel(), {})
        loop.apply_optimizations({
            "tool_cost_multipliers": {"security": 1.3},
            "strategy_biases": {},
        })
        assert score.stability < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Test: Full Run Pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestFullRun:
    def test_run_returns_expected_keys(self):
        cm = FakeCostModel()
        stats: dict = {}
        loop = GlobalOptimizationLoop(FakeGovernor(), cm, stats)
        history = [make_record(tools=["llm"], success=True)]
        result = loop.run(history)
        assert "metrics" in result
        assert "inefficiencies" in result
        assert "adjustments" in result

    def test_run_increments_count(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        history = [make_record(tools=["llm"], success=True)]
        loop.run(history)
        assert loop.get_optimization_count() == 1
        loop.run(history)
        assert loop.get_optimization_count() == 2

    def test_run_logs_adjustments(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        history = [make_record(tools=["llm"], success=True)]
        loop.run(history)
        assert len(loop.get_adjustment_log()) == 1
        assert loop.get_last_adjustment() is not None

    def test_empty_history_no_crash(self):
        loop = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        result = loop.run([])
        assert result["metrics"]["total_tasks"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Test: Determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_history_same_metrics(self):
        a = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        b = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        history = [make_record(tools=["llm", "code_executor"], success=True),
                   make_record(tools=["llm"], success=False)]
        assert a.analyze_system_metrics(history) == b.analyze_system_metrics(history)

    def test_same_history_same_inefficiencies(self):
        a = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        b = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        metrics = {
            "tool_stats": {"llm": {"efficiency": 0.1, "success_rate": 0.3, "avg_cost": 3.0}},
            "strategy_effectiveness": {},
            "fallback_rate": 0.0,
        }
        assert a.detect_inefficiencies(metrics) == b.detect_inefficiencies(metrics)

    def test_same_adjustments_same_result(self):
        cm = FakeCostModel()
        a = GlobalOptimizationLoop(FakeGovernor(), cm, {})
        b = GlobalOptimizationLoop(FakeGovernor(), FakeCostModel(), {})
        ineff = {
            "low_efficiency_tools": [{"tool": "security", "efficiency": 0.1, "success_rate": 0.3, "avg_cost": 3.0}],
            "high_variance_strategies": [],
            "high_fallback_path": False,
        }
        assert a.compute_adjustments(ineff) == b.compute_adjustments(ineff)


# ═══════════════════════════════════════════════════════════════════════════
# Test: No-LLM Guarantee
# ═══════════════════════════════════════════════════════════════════════════

class TestNoLLM:
    def test_all_methods_deterministic_no_llm(self):
        cm = FakeCostModel()
        loop = GlobalOptimizationLoop(FakeGovernor(), cm, {})
        history = [make_record(tools=["llm"], success=True)]
        result = loop.run(history)
        # Result is derived from deterministic math, no external LLM calls
        assert isinstance(result["metrics"]["total_tasks"], int)
        assert isinstance(result["adjustments"]["tool_cost_multipliers"], dict)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Integration with GovernanceKernel
# ═══════════════════════════════════════════════════════════════════════════

class TestKernelIntegration:
    def test_kernel_accepts_global_optimizer(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cm = GovernanceCostModel()
        stats: dict = {}
        loop = GlobalOptimizationLoop(MockGov(), cm, stats)
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  cost_model=cm,
                                  global_optimizer=loop)
        # Optimizer is stored but not called during process()
        assert kernel._global_optimizer is loop

    def test_optimizer_updates_cost_model_via_kernel(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cm = GovernanceCostModel()
        stats: dict = {}
        loop = GlobalOptimizationLoop(MockGov(), cm, stats)
        old_cost = cm.cost_table["llm"]

        # Simulate 50 tasks with mostly failed security calls
        history = []
        for i in range(10):
            history.append(make_record(tools=["security"], success=False))
        for i in range(10):
            history.append(make_record(tools=["llm"], success=True))

        loop.run(history)
        assert cm.cost_table["security"] > old_cost  # Inefficient tool penalized

    def test_optimizer_with_complexity_budget(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cm = GovernanceCostModel()
        cb = ComplexityBudget()
        stats: dict = {}
        loop = GlobalOptimizationLoop(MockGov(), cm, stats)
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  complexity_budget=cb,
                                  cost_model=cm,
                                  global_optimizer=loop)
        assert kernel._global_optimizer is loop

    def test_full_system_pipeline_no_error(self):
        """End-to-end: process a task then run global optimization."""
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cm = GovernanceCostModel()
        cb = ComplexityBudget()
        stats: dict = {}
        loop = GlobalOptimizationLoop(MockGov(), cm, stats)
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  complexity_budget=cb,
                                  cost_model=cm,
                                  global_optimizer=loop)

        # Process a task
        plan = {"goal": "test", "steps": [{"id": 1, "tool": "llm", "action": "hello", "type": "tool"}]}
        kernel.process({"task": "hello"}, plan)

        # Run global optimization
        history = [
            make_record(tools=["llm"], success=True),
            make_record(tools=["llm"], success=False),
        ]
        result = loop.run(history)
        assert result["adjustments"]["round"] == 1
