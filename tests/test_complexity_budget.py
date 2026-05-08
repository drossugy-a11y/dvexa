"""Tests for Complexity Budget v1."""
import pytest
from governance.complexity_budget import ComplexityBudget
from governance.governance_kernel import GovernanceKernel


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_step(step_id: int, tool: str = "llm", action: str = "do",
              type: str = "tool") -> dict:
    return {"id": step_id, "tool": tool, "action": action, "type": type}


def make_plan(steps: list[dict]) -> dict:
    return {"goal": "test", "steps": steps}


# ═══════════════════════════════════════════════════════════════════════════
# Test: Budget Assignment
# ═══════════════════════════════════════════════════════════════════════════

class TestBudgetAssignment:
    def test_simple_task_gets_low_budget(self):
        cb = ComplexityBudget()
        budget = cb.assign_budget({"task": "hello world"})
        assert budget["profile"] == "simple"
        assert budget["max_steps"] == 5

    def test_normal_task_gets_default_budget(self):
        cb = ComplexityBudget()
        budget = cb.assign_budget({"task": "do something regular"})
        assert budget["profile"] == "normal"
        assert budget["max_steps"] == 8

    def test_analysis_task_gets_high_budget(self):
        cb = ComplexityBudget()
        budget = cb.assign_budget({"task": "分析这份报告的数据"})
        assert budget["profile"] == "analysis"
        assert budget["max_steps"] == 10

    def test_network_task_gets_low_fanout(self):
        cb = ComplexityBudget()
        budget = cb.assign_budget({"task": "fetch http data"})
        assert budget["profile"] == "network"
        assert budget["max_tool_fanout"] == 2

    def test_empty_task_gets_normal(self):
        cb = ComplexityBudget()
        budget = cb.assign_budget({})
        assert budget["profile"] == "normal"

    def test_budget_has_all_expected_keys(self):
        cb = ComplexityBudget()
        budget = cb.assign_budget({"task": "test"})
        for key in ("profile", "max_steps", "max_tool_fanout",
                     "max_governance_depth", "max_decision_nodes"):
            assert key in budget


# ═══════════════════════════════════════════════════════════════════════════
# Test: Plan Check
# ═══════════════════════════════════════════════════════════════════════════

class TestPlanCheck:
    def test_no_violations_for_normal_plan(self):
        cb = ComplexityBudget()
        plan = make_plan([make_step(1, "llm", "analyze")])
        budget = {"max_steps": 8, "max_tool_fanout": 3, "max_governance_depth": 4}
        result = cb.check_plan(plan, budget)
        assert result["_budget_violations"] == []

    def test_step_overflow_detected(self):
        cb = ComplexityBudget()
        steps = [make_step(i, "llm", f"s{i}") for i in range(10)]
        plan = make_plan(steps)
        budget = {"max_steps": 5, "max_tool_fanout": 3, "max_governance_depth": 4}
        result = cb.check_plan(plan, budget)
        violations = result["_budget_violations"]
        assert any(v["rule"] == "max_steps" for v in violations)
        assert violations[0]["actual"] == 10
        assert violations[0]["limit"] == 5

    def test_tool_fanout_detected(self):
        cb = ComplexityBudget()
        steps = [
            make_step(1, "llm", "a"),
            make_step(2, "code_executor", "b"),
            make_step(3, "http_request", "c"),
            make_step(4, "github", "d"),
            make_step(5, "security", "e"),
        ]
        plan = make_plan(steps)
        budget = {"max_steps": 8, "max_tool_fanout": 2, "max_governance_depth": 4}
        result = cb.check_plan(plan, budget)
        violations = result["_budget_violations"]
        assert any(v["rule"] == "max_tool_fanout" for v in violations)

    def test_governance_depth_detected(self):
        cb = ComplexityBudget()
        steps = [
            make_step(1, "security", "scan"),
            make_step(2, "security", "verify"),
            make_step(3, "security", "report"),
            make_step(4, "security", "audit"),
        ]
        plan = make_plan(steps)
        budget = {"max_steps": 8, "max_tool_fanout": 3, "max_governance_depth": 2}
        result = cb.check_plan(plan, budget)
        violations = result["_budget_violations"]
        assert any(v["rule"] == "max_governance_depth" for v in violations)

    def test_empty_plan_no_violations(self):
        cb = ComplexityBudget()
        budget = {"max_steps": 8, "max_tool_fanout": 3, "max_governance_depth": 4}
        result = cb.check_plan(None, budget)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Test: Enforce
# ═══════════════════════════════════════════════════════════════════════════

class TestEnforce:
    def test_step_overflow_truncated(self):
        cb = ComplexityBudget()
        steps = [make_step(i, "llm", f"s{i}") for i in range(15)]
        plan = make_plan(steps)
        budget = {"max_steps": 5, "max_tool_fanout": 3, "max_governance_depth": 4}
        result = cb.enforce(plan, budget)
        assert len(result["steps"]) == 5

    def test_under_limit_unchanged(self):
        cb = ComplexityBudget()
        steps = [make_step(1, "llm", "a")]
        plan = make_plan(steps)
        budget = {"max_steps": 8, "max_tool_fanout": 3, "max_governance_depth": 4}
        result = cb.enforce(plan, budget)
        assert len(result["steps"]) == 1

    def test_excess_tools_downgraded_to_llm(self):
        cb = ComplexityBudget()
        steps = [
            make_step(1, "llm", "a"),
            make_step(2, "code_executor", "b"),
            make_step(3, "http_request", "c"),
            make_step(4, "github", "d"),
        ]
        plan = make_plan(steps)
        budget = {"max_steps": 8, "max_tool_fanout": 2, "max_governance_depth": 4}
        result = cb.enforce(plan, budget)
        # Only 2 tools should remain; excess tools → llm
        tools_after = {s["tool"] for s in result["steps"]}
        assert len(tools_after - {"llm"}) <= 2

    def test_empty_plan_unchanged(self):
        cb = ComplexityBudget()
        budget = {"max_steps": 8, "max_tool_fanout": 3, "max_governance_depth": 4}
        assert cb.enforce(None, budget) is None
        assert cb.enforce({}, budget) == {}
        assert cb.enforce({"goal": "x"}, budget) == {"goal": "x"}

    def test_governance_depth_enforced(self):
        cb = ComplexityBudget()
        steps = [
            make_step(1, "security", "s1"),
            make_step(2, "security", "s2"),
            make_step(3, "security", "s3"),
            make_step(4, "security", "s4"),
            make_step(5, "llm", "done"),
        ]
        plan = make_plan(steps)
        budget = {"max_steps": 8, "max_tool_fanout": 3, "max_governance_depth": 2}
        result = cb.enforce(plan, budget)
        # max_gov_depth=2, so at most 2 consecutive security steps
        security_run = 0
        max_run = 0
        for s in result["steps"]:
            if s.get("tool") == "security":
                security_run += 1
                max_run = max(max_run, security_run)
            else:
                security_run = 0
        assert max_run <= 2


# ═══════════════════════════════════════════════════════════════════════════
# Test: Complexity Score
# ═══════════════════════════════════════════════════════════════════════════

class TestComplexityScore:
    def test_empty_plan_zero(self):
        cb = ComplexityBudget()
        assert cb.estimate_complexity(None) == 0.0
        assert cb.estimate_complexity({}) == 0.0

    def test_single_step_low_score(self):
        cb = ComplexityBudget()
        plan = make_plan([make_step(1, "llm", "hello")])
        score = cb.estimate_complexity(plan)
        assert 0.0 < score < 0.5

    def test_complex_plan_higher_score(self):
        cb = ComplexityBudget()
        plan = make_plan([
            make_step(1, t, f"action_{i}")
            for i, t in enumerate(["llm", "code_executor", "http_request", "github", "security"])
        ])
        complex_score = cb.estimate_complexity(plan)

        simple = make_plan([make_step(1, "llm", "hi")])
        simple_score = cb.estimate_complexity(simple)

        assert complex_score > simple_score

    def test_score_range(self):
        cb = ComplexityBudget()
        steps = [make_step(i, "llm", f"long action description for step {i}") for i in range(20)]
        plan = make_plan(steps)
        score = cb.estimate_complexity(plan)
        assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Test: Determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_input_same_budget(self):
        a = ComplexityBudget()
        b = ComplexityBudget()
        assert a.assign_budget({"task": "分析报告"}) == b.assign_budget({"task": "分析报告"})

    def test_same_input_same_enforce(self):
        a = ComplexityBudget()
        b = ComplexityBudget()
        steps = [make_step(i, "llm", f"s{i}") for i in range(12)]
        plan = make_plan(steps)
        budget = {"max_steps": 5, "max_tool_fanout": 3, "max_governance_depth": 4}
        assert a.enforce(plan, budget) == b.enforce(plan, budget)


# ═══════════════════════════════════════════════════════════════════════════
# Test: No-LLM Guarantee
# ═══════════════════════════════════════════════════════════════════════════

class TestNoLLM:
    def test_all_methods_deterministic_no_llm(self):
        cb = ComplexityBudget()
        # All methods should return the same results without any LLM
        plan = make_plan([make_step(1, "code_executor", "run")])
        budget = cb.assign_budget({"task": "run code"})
        assert "llm" not in str(budget)  # just checking no LLM involvement
        check = cb.check_plan(plan, budget)
        assert "_budget_violations" in check
        enforce = cb.enforce(plan, budget)
        assert "steps" in enforce
        score = cb.estimate_complexity(plan)
        assert isinstance(score, float)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Kernel Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestKernelIntegration:
    def test_kernel_with_budget_caps_steps(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cb = ComplexityBudget()
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  complexity_budget=cb)
        steps = [make_step(i, "llm", f"s{i}") for i in range(15)]
        plan = make_plan(steps)
        result = kernel.process({"task": "hello"}, plan)
        # simple budget → max_steps=5
        assert len(result["filtered_plan"]["steps"]) == 5

    def test_kernel_without_budget_unchanged(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        kernel = GovernanceKernel(skill_governor=MockGov())
        steps = [make_step(i, "llm", f"s{i}") for i in range(15)]
        plan = make_plan(steps)
        result = kernel.process({}, plan)
        assert len(result["filtered_plan"]["steps"]) == 15

    def test_kernel_with_budget_plus_stabilizer(self):
        """budget 前置截断 + stabilizer 后置兜底同时工作。"""
        from governance.stabilizer import GovernanceStabilizer

        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cb = ComplexityBudget()
        st = GovernanceStabilizer()
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  complexity_budget=cb,
                                  stabilizer=st)
        steps = [make_step(i, "llm", f"s{i}") for i in range(15)]
        plan = make_plan(steps)
        result = kernel.process({"task": "hello"}, plan)
        # budget: simple → max_steps=5 (pre-cut)
        # stabilizer: also caps at 8 (but already ≤ 8)
        assert len(result["filtered_plan"]["steps"]) == 5

    def test_kernel_budget_does_not_change_strategy(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        cb = ComplexityBudget()
        kernel_no = GovernanceKernel(skill_governor=MockGov())
        kernel_budget = GovernanceKernel(skill_governor=MockGov(),
                                         complexity_budget=cb)
        plan = make_plan([make_step(1, "llm", "analyze")])
        r1 = kernel_no.process({}, plan)
        r2 = kernel_budget.process({"task": "hello"}, plan)
        assert r1["strategy"] == r2["strategy"]
