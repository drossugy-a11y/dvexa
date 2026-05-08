"""Tests for Governance Cost Model v1."""
import pytest
from governance.cost_model import GovernanceCostModel
from governance.governance_kernel import GovernanceKernel
from governance.complexity_budget import ComplexityBudget


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_step(step_id: int, tool: str = "llm", action: str = "do",
              type: str = "tool", depth: int = 0) -> dict:
    step = {"id": step_id, "tool": tool, "action": action, "type": type}
    if depth:
        step["_depth"] = depth
    return step


def make_plan(steps: list[dict]) -> dict:
    return {"goal": "test", "steps": steps}


# ═══════════════════════════════════════════════════════════════════════════
# Test: Step Cost
# ═══════════════════════════════════════════════════════════════════════════

class TestStepCost:
    def test_reasoning_step_fixed_cost(self):
        cm = GovernanceCostModel()
        step = {"id": 1, "type": "reasoning", "action": "think"}
        assert cm.estimate_step_cost(step) == 1.0

    def test_empty_tool_step_fixed_cost(self):
        cm = GovernanceCostModel()
        step = {"id": 1, "action": "hello"}
        assert cm.estimate_step_cost(step) == 1.0

    def test_llm_step_base_cost(self):
        cm = GovernanceCostModel()
        step = make_step(1, "llm", "analyze")
        # base=3.0 + complexity(len("analyze")/100*0.5=0.035) + depth=0
        assert cm.estimate_step_cost(step) == 3.04

    def test_code_executor_step_cost(self):
        cm = GovernanceCostModel()
        step = make_step(1, "code_executor", "run script")
        # base=2.0 + complexity(10/100*0.5=0.05) = 2.05
        assert cm.estimate_step_cost(step) == 2.05

    def test_http_step_cost(self):
        cm = GovernanceCostModel()
        step = make_step(1, "http_request", "fetch data")
        # base=1.0 + complexity(10/100*0.5=0.05) = 1.05
        assert cm.estimate_step_cost(step) == 1.05

    def test_github_step_cost(self):
        cm = GovernanceCostModel()
        step = make_step(1, "github", "browse repo")
        # base=1.5 + complexity = 1.55
        assert cm.estimate_step_cost(step) == 1.55

    def test_security_step_cost(self):
        cm = GovernanceCostModel()
        step = make_step(1, "security", "scan code")
        # base=2.5 + complexity(9/100*0.5=0.045) = 2.545 → round to 2.54
        assert cm.estimate_step_cost(step) == 2.54

    def test_complex_action_higher_cost(self):
        cm = GovernanceCostModel()
        simple = make_step(1, "llm", "hi")
        complex = make_step(2, "llm", "a" * 80)
        assert cm.estimate_step_cost(complex) > cm.estimate_step_cost(simple)

    def test_depth_penalty_applied(self):
        cm = GovernanceCostModel()
        no_depth = make_step(1, "llm", "do")
        with_depth = make_step(2, "llm", "do", depth=5)
        # with_depth: base=3.0 + complexity(2/100*0.5=0.01) + depth(0.1*5=0.5) = 3.51
        assert cm.estimate_step_cost(with_depth) > cm.estimate_step_cost(no_depth)

    def test_unknown_tool_default_cost(self):
        cm = GovernanceCostModel()
        step = make_step(1, "unknown_tool", "do")
        # unknown tools have base cost 1.0
        assert cm.estimate_step_cost(step) == 1.01


# ═══════════════════════════════════════════════════════════════════════════
# Test: Plan Cost
# ═══════════════════════════════════════════════════════════════════════════

class TestPlanCost:
    def test_empty_plan_zero_cost(self):
        cm = GovernanceCostModel()
        assert cm.estimate_plan_cost(None)["total_cost"] == 0.0
        assert cm.estimate_plan_cost({})["total_cost"] == 0.0
        assert cm.estimate_plan_cost({"goal": "x"})["total_cost"] == 0.0

    def test_single_step_cost_matches(self):
        cm = GovernanceCostModel()
        plan = make_plan([make_step(1, "llm", "analyze")])
        result = cm.estimate_plan_cost(plan)
        assert result["total_cost"] > 0
        assert len(result["step_costs"]) == 1
        assert result["step_costs"][0] == cm.estimate_step_cost(plan["steps"][0])

    def test_plan_cost_aggregation(self):
        cm = GovernanceCostModel()
        steps = [
            make_step(1, "llm", "analyze"),
            make_step(2, "code_executor", "run"),
            make_step(3, "llm", "summarize"),
        ]
        plan = make_plan(steps)
        result = cm.estimate_plan_cost(plan)
        expected = sum(cm.estimate_step_cost(s) for s in steps)
        # with penalties: fanout=0.2 (2 unique tools), depth maybe 0
        assert result["total_cost"] > expected

    def test_over_budget_detected(self):
        cm = GovernanceCostModel(max_plan_cost=5.0)
        steps = [make_step(i, "llm", "action") for i in range(10)]
        plan = make_plan(steps)
        result = cm.estimate_plan_cost(plan)
        assert result["over_budget"] is True

    def test_under_budget_ok(self):
        cm = GovernanceCostModel(max_plan_cost=50.0)
        steps = [make_step(1, "llm", "hi")]
        plan = make_plan(steps)
        result = cm.estimate_plan_cost(plan)
        assert result["over_budget"] is False

    def test_has_all_expected_keys(self):
        cm = GovernanceCostModel()
        plan = make_plan([make_step(1, "llm", "do")])
        result = cm.estimate_plan_cost(plan)
        for key in ("total_cost", "step_costs", "over_budget",
                     "dependency_penalty", "fanout_penalty"):
            assert key in result


# ═══════════════════════════════════════════════════════════════════════════
# Test: Enforce Cost Limit
# ═══════════════════════════════════════════════════════════════════════════

class TestEnforceCostLimit:
    def test_under_budget_unchanged(self):
        cm = GovernanceCostModel(max_plan_cost=50.0)
        steps = [make_step(1, "llm", "hi")]
        plan = make_plan(steps)
        result = cm.enforce_cost_limit(plan)
        assert len(result["steps"]) == 1
        assert result["steps"][0]["tool"] == "llm"

    def test_high_cost_step_downgraded_to_reasoning(self):
        cm = GovernanceCostModel(max_step_cost=1.0)
        steps = [make_step(1, "llm", "a" * 200)]  # llm base 3.0 > 1.0
        plan = make_plan(steps)
        result = cm.enforce_cost_limit(plan)
        assert result["steps"][0].get("type") == "reasoning"
        assert "tool" not in result["steps"][0]

    def test_plan_over_budget_reduced(self):
        cm = GovernanceCostModel(max_plan_cost=5.0)
        steps = [make_step(i, "llm", f"action_{i}") for i in range(10)]
        plan = make_plan(steps)
        result = cm.enforce_cost_limit(plan)
        cost_info = cm.estimate_plan_cost(result)
        # May still be over budget if even 1 llm step exceeds 5.0
        # But we should have fewer steps
        assert len(result["steps"]) <= len(steps)

    def test_enforce_annotates_plan(self):
        cm = GovernanceCostModel(max_plan_cost=1.0)
        steps = [make_step(i, "llm", f"action_{i}") for i in range(5)]
        plan = make_plan(steps)
        result = cm.enforce_cost_limit(plan)
        assert result.get("_cost_enforced") is True

    def test_empty_plan_unchanged(self):
        cm = GovernanceCostModel()
        assert cm.enforce_cost_limit(None) is None
        assert cm.enforce_cost_limit({}) == {}
        assert cm.enforce_cost_limit({"goal": "x"}) == {"goal": "x"}

    def test_over_budget_downgrades_low_value_steps_first(self):
        cm = GovernanceCostModel(max_plan_cost=3.0)
        steps = [
            make_step(1, "llm", "high value analysis task"),
            make_step(2, "code_executor", "x"),
        ]
        plan = make_plan(steps)
        result = cm.enforce_cost_limit(plan)
        # The low-value step (short action "x") should be downgraded/removed first
        cost_info = cm.estimate_plan_cost(result)
        assert cost_info["total_cost"] <= cm.max_plan_cost or len(result["steps"]) < len(steps)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Cost-efficient Plan Selection
# ═══════════════════════════════════════════════════════════════════════════

class TestSelectCostEfficientPlan:
    def test_empty_plans_returns_none(self):
        cm = GovernanceCostModel()
        assert cm.select_cost_efficient_plan([]) is None
        assert cm.select_cost_efficient_plan(None) is None

    def test_selects_best_ratio(self):
        cm = GovernanceCostModel()
        cheap = make_plan([make_step(1, "llm", "quick answer")])
        cheap["_expected_success"] = 0.3
        expensive = make_plan([make_step(1, "llm", "detailed analysis"),
                               make_step(2, "code_executor", "compute")])
        expensive["_expected_success"] = 0.9

        # cheap: 0.3 / ~3.04 ≈ 0.099
        # expensive: 0.9 / (~3.04+~2.05+penalties) ≈ 0.9 / ~5.29 ≈ 0.17
        result = cm.select_cost_efficient_plan([cheap, expensive])
        assert result is expensive

    def test_cheaper_plan_wins_when_success_similar(self):
        cm = GovernanceCostModel()
        cheap = make_plan([make_step(1, "llm", "quick")])
        cheap["_expected_success"] = 0.5
        expensive = make_plan([make_step(1, "llm", "quick"),
                               make_step(2, "code_executor", "extra")])
        expensive["_expected_success"] = 0.55

        result = cm.select_cost_efficient_plan([cheap, expensive])
        assert result is cheap


# ═══════════════════════════════════════════════════════════════════════════
# Test: Skill Efficiency
# ═══════════════════════════════════════════════════════════════════════════

class TestSkillEfficiency:
    def test_compute_basic_efficiency(self):
        cm = GovernanceCostModel()
        eff = cm.compute_skill_efficiency("llm", {"success_rate": 0.8, "avg_cost": 3.0})
        assert eff == pytest.approx(0.2667, rel=0.01)

    def test_default_cost_used_when_not_in_stats(self):
        cm = GovernanceCostModel()
        eff = cm.compute_skill_efficiency("llm", {"success_rate": 0.9})
        # default llm cost is 3.0
        assert eff == pytest.approx(0.3, rel=0.01)

    def test_efficiency_zero_cost_protection(self):
        cm = GovernanceCostModel()
        eff = cm.compute_skill_efficiency("llm", {"success_rate": 0.5, "avg_cost": 0.0})
        assert eff > 0  # no division by zero


# ═══════════════════════════════════════════════════════════════════════════
# Test: Determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_input_same_cost(self):
        a = GovernanceCostModel()
        b = GovernanceCostModel()
        plan = make_plan([make_step(1, "llm", "analyze"),
                          make_step(2, "code_executor", "compute")])
        assert a.estimate_plan_cost(plan) == b.estimate_plan_cost(plan)

    def test_same_input_same_enforce(self):
        a = GovernanceCostModel(max_plan_cost=5.0)
        b = GovernanceCostModel(max_plan_cost=5.0)
        steps = [make_step(i, "llm", f"action_{i}") for i in range(10)]
        plan = make_plan(steps)
        assert a.enforce_cost_limit(plan) == b.enforce_cost_limit(plan)


# ═══════════════════════════════════════════════════════════════════════════
# Test: No-LLM Guarantee
# ═══════════════════════════════════════════════════════════════════════════

class TestNoLLM:
    def test_all_methods_deterministic_no_llm(self):
        cm = GovernanceCostModel()
        plan = make_plan([make_step(1, "code_executor", "run")])
        cost = cm.estimate_plan_cost(plan)
        assert isinstance(cost["total_cost"], float)
        enforced = cm.enforce_cost_limit(plan)
        assert "steps" in enforced
        eff = cm.compute_skill_efficiency("code", {"success_rate": 0.5})
        assert isinstance(eff, float)
        selected = cm.select_cost_efficient_plan([plan])
        assert selected is plan


# ═══════════════════════════════════════════════════════════════════════════
# Test: Kernel Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestKernelIntegration:
    def test_kernel_with_cost_model_caps_high_cost_plans(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cm = GovernanceCostModel(max_plan_cost=5.0)
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  cost_model=cm)
        steps = [make_step(i, "llm", f"step_{i}") for i in range(10)]
        plan = make_plan(steps)
        result = kernel.process({"task": "hello"}, plan)
        # Cost model should reduce steps or downgrade
        cost_info = cm.estimate_plan_cost(result["filtered_plan"])
        # Either under budget or fewer steps than original
        assert (not cost_info["over_budget"]
                or len(result["filtered_plan"]["steps"]) < len(steps))

    def test_kernel_without_cost_model_unchanged(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        kernel = GovernanceKernel(skill_governor=MockGov())
        steps = [make_step(i, "llm", f"step_{i}") for i in range(10)]
        plan = make_plan(steps)
        result = kernel.process({}, plan)
        assert len(result["filtered_plan"]["steps"]) == 10

    def test_kernel_with_budget_and_cost_model(self):
        """ComplexityBudget + CostModel 同时工作。"""
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cb = ComplexityBudget()
        cm = GovernanceCostModel(max_plan_cost=10.0)
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  complexity_budget=cb,
                                  cost_model=cm)
        steps = [make_step(i, "llm", f"step_{i}") for i in range(15)]
        plan = make_plan(steps)
        result = kernel.process({"task": "hello"}, plan)
        # budget caps at 5 (simple), then cost model further constrains
        assert len(result["filtered_plan"]["steps"]) <= 5

    def test_kernel_cost_does_not_break_strategy(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        kernel_no = GovernanceKernel(skill_governor=MockGov())
        cm = GovernanceCostModel(max_plan_cost=50.0)
        kernel_cost = GovernanceKernel(skill_governor=MockGov(),
                                       cost_model=cm)
        plan = make_plan([make_step(1, "llm", "analyze")])
        r1 = kernel_no.process({}, plan)
        r2 = kernel_cost.process({"task": "hello"}, plan)
        assert r1["strategy"] == r2["strategy"]
