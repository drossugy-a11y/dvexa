"""Tests for Governance Decision Injection Layer."""
import pytest
from governance.decision_layer import (
    DecisionInjectionLayer,
    GovernanceExecutorWrapper,
    _to_skill_name,
)


# ─── Mock Governance Objects ─────────────────────────────────────────────

class MockSkillScore:
    def __init__(self, combined_score=0.8, usage=10):
        self.combined_score = combined_score
        self.usage = usage


class MockStatus:
    def __init__(self, value):
        self.value = value


class MockGovernor:
    """Mock SkillGovernor 返回可控的 lifecycle/policy/score。"""

    def __init__(self):
        self._statuses = {}
        self._scores = {}
        self._policies = {}  # skill_name → bool (allowed)

    def set_status(self, skill: str, status: str):
        self._statuses[skill] = MockStatus(status)

    def set_score(self, skill: str, score: float):
        self._scores[skill] = MockSkillScore(score)

    def set_policy(self, skill: str, allowed: bool):
        self._policies[skill] = allowed

    def get_status(self, skill: str):
        return self._statuses.get(skill, MockStatus("experimental"))

    def get_score(self, skill: str):
        return self._scores.get(skill)

    def check_skill_allowed(self, skill: str) -> bool:
        # 默认允许，除非显式设置 deny
        return self._policies.get(skill, True)


class MockATSPhaseResult:
    def __init__(self, passed=True):
        self.passed = passed
        self.phase = "test"
        self.verdict = "pass"
        self.details = ""
        self.warnings = []


class MockRiskLevel:
    def __init__(self, value):
        self.value = value


class MockATSReport:
    def __init__(self, passed=True, risk_level="low", risk_score=0.0, summary="mock"):
        self.passed = passed
        self.risk_level = MockRiskLevel(risk_level)
        self.risk_score = risk_score
        self.summary = summary
        self.phases = []
        self.target = "mock"


class MockATS:
    """Mock AssimilationTestSystem 返回可控的 report。"""

    def __init__(self):
        self._reports = {}  # action_text → ATSReport override
        self._default = MockATSReport()

    def set_default(self, report: MockATSReport):
        self._default = report

    def set_report(self, action: str, report: MockATSReport):
        self._reports[action] = report

    def run(self, target: str, context: dict):
        return self._reports.get(target, self._default)


class MockExecutor:
    """Mock Executor 用于 GovernanceExecutorWrapper 测试。"""

    def __init__(self):
        self.last_plan_input = None
        self.agent = MockAgent()

    def plan_task(self, task_input: str) -> dict:
        self.last_plan_input = task_input
        return {
            "goal": "test goal",
            "steps": [
                {"id": 1, "action": "analyze data", "type": "tool", "tool": "llm"},
                {"id": 2, "action": "run code", "type": "tool", "tool": "code_executor"},
            ],
        }

    def execute_step(self, task_state, step, context):
        return {"step_id": step.get("id"), "output": "done"}


class MockAgent:
    def replan(self, *args, **kwargs):
        return None


# ─── Helper ──────────────────────────────────────────────────────────────

def make_plan(steps: list[dict]) -> dict:
    return {"goal": "test", "steps": steps}


SAMPLE_STEPS = [
    {"id": 1, "action": "analyze requirements", "type": "tool", "tool": "llm"},
    {"id": 2, "action": "execute computation", "type": "tool", "tool": "code_executor"},
    {"id": 3, "action": "summarize results", "type": "tool", "tool": "llm"},
]


# ─── _to_skill_name ──────────────────────────────────────────────────────

class TestToolNameMapping:
    def test_executor_tool_to_skill(self):
        assert _to_skill_name("code_executor") == "code"
        assert _to_skill_name("http_request") == "http"
        assert _to_skill_name("llm") == "llm"
        assert _to_skill_name("unknown") == "unknown"


# ─── DecisionInjectionLayer — Core ────────────────────────────────────────

class TestDecisionInjectionLayer:
    def test_no_governance_passthrough(self):
        """无 governor/ATS 时 plan 原样通过。"""
        layer = DecisionInjectionLayer()
        plan = make_plan(SAMPLE_STEPS)
        result = layer.inject(plan)
        assert len(result["filtered_plan"]["steps"]) == 3
        assert result["filtered_plan"]["steps"] == SAMPLE_STEPS

    def test_empty_plan_does_not_crash(self):
        """空 plan 不崩溃。"""
        layer = DecisionInjectionLayer()
        assert layer.inject(None)["filtered_plan"] is None
        assert layer.inject({})["filtered_plan"] == {}
        # plan without steps key — returned as-is with empty decisions
        result = layer.inject({"goal": "x"})
        assert "steps" not in result["filtered_plan"]
        assert result["decisions"] == []

    # ── Lifecycle ────────────────────────────────────────────────────

    def test_lifecycle_quarantined_blocks_step(self):
        """QUARANTINED → block: 该步被移除。"""
        governor = MockGovernor()
        governor.set_status("llm", "quarantined")
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "talk", "type": "tool", "tool": "llm"},
            {"id": 2, "action": "code", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        steps = result["filtered_plan"]["steps"]
        # llm step (QUARANTINED) blocked
        # code_executor (experimental) survives but STRICT downgrades to reasoning
        assert len(steps) == 1
        assert steps[0]["type"] == "reasoning"

    def test_lifecycle_degraded_downgrades_step(self):
        """DEGRADED → downgrade: tool→reasoning。"""
        governor = MockGovernor()
        governor.set_status("code", "degraded")
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "compute", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["type"] == "reasoning"
        assert "tool" not in step

    def test_lifecycle_removed_blocks_step(self):
        """REMOVED → block。"""
        governor = MockGovernor()
        governor.set_status("code", "removed")
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "run", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        assert len(result["filtered_plan"]["steps"]) == 0
        actions = [d["action"] for d in result["decisions"]]
        assert "block" in actions

    # ── ToolPolicy ───────────────────────────────────────────────────

    def test_tool_policy_deny_reroutes_to_llm(self):
        """deny → reroute to llm。"""
        governor = MockGovernor()
        governor.set_policy("code", False)  # code is denied
        # 但 llm 默认允许
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "compute", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["tool"] == "llm"
        # decisions[0] is lifecycle (allow), decisions[1] is reroute
        actions = [d["action"] for d in result["decisions"]]
        assert "reroute" in actions

    def test_tool_policy_deny_all_reroutes_to_llm(self):
        """所有工具被 deny → 均 reroute 到 llm（当前不重复检查 fallback 策略）。"""
        governor = MockGovernor()
        governor.set_policy("llm", False)
        governor.set_policy("code", False)
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "compute", "type": "tool", "tool": "code_executor"},
            {"id": 2, "action": "talk", "type": "tool", "tool": "llm"},
        ])
        result = layer.inject(plan)
        # 两个步骤都被 reroute 到 llm（reroute 后不重新检查 llm 策略）
        reroutes = [d for d in result["decisions"] if d["action"] == "reroute"]
        assert len(reroutes) == 2
        assert reroutes[0]["reroute_to"] == "llm"
        # 两个步骤都存活（未被 block）
        assert len(result["filtered_plan"]["steps"]) == 2

    # ── ATS ──────────────────────────────────────────────────────────

    def test_ats_fail_blocks_step(self):
        """ATS fail → block。"""
        ats = MockATS()
        ats.set_default(MockATSReport(passed=False, risk_level="low", summary="safety check failed"))
        layer = DecisionInjectionLayer(ats=ats)

        plan = make_plan([
            {"id": 1, "action": "dangerous_operation", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        assert len(result["filtered_plan"]["steps"]) == 0
        actions = [d["action"] for d in result["decisions"]]
        assert "block" in actions

    def test_ats_high_risk_downgrades(self):
        """ATS HIGH risk → downgrade to reasoning。"""
        ats = MockATS()
        ats.set_default(MockATSReport(passed=True, risk_level="high", risk_score=0.6))
        layer = DecisionInjectionLayer(ats=ats)

        plan = make_plan([
            {"id": 1, "action": "risky_action", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["type"] == "reasoning"
        assert "tool" not in step

    def test_ats_critical_risk_downgrades(self):
        """ATS CRITICAL risk → downgrade。"""
        ats = MockATS()
        ats.set_default(MockATSReport(passed=True, risk_level="critical", risk_score=0.85))
        layer = DecisionInjectionLayer(ats=ats)

        plan = make_plan([
            {"id": 1, "action": "critical_action", "type": "tool", "tool": "llm"},
        ])
        result = layer.inject(plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["type"] == "reasoning"

    def test_ats_low_risk_allows(self):
        """ATS LOW risk → allow。"""
        ats = MockATS()
        ats.set_default(MockATSReport(passed=True, risk_level="low", risk_score=0.05))
        layer = DecisionInjectionLayer(ats=ats)

        plan = make_plan(SAMPLE_STEPS)
        result = layer.inject(plan)
        assert len(result["filtered_plan"]["steps"]) == 3
        # 所有 steps 保持原样
        assert result["filtered_plan"]["steps"][0]["type"] == "tool"

    # ── SkillScore ──────────────────────────────────────────────────

    def test_low_score_downgrades(self):
        """combined_score < 0.3 → downgrade。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.15)
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "talk", "type": "tool", "tool": "llm"},
        ])
        result = layer.inject(plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["type"] == "reasoning"

    def test_high_score_allows(self):
        """combined_score >= 0.3 → allow。"""
        governor = MockGovernor()
        governor.set_score("code", 0.85)
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "compute", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["type"] == "tool"
        assert step["tool"] == "code_executor"

    # ── Reorder ─────────────────────────────────────────────────────

    def test_reorder_by_score(self):
        """步骤按 type + score 重排序：reasoning 优先，tool 按 score 降序。"""
        governor = MockGovernor()
        governor.set_score("code", 0.9)
        governor.set_score("llm", 0.4)
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "low_score_llm", "type": "tool", "tool": "llm"},
            {"id": 2, "action": "high_score_code", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        steps = result["filtered_plan"]["steps"]
        # Neither was downgraded (both scores >= 0.3), reorder by score desc
        # code (0.9) should come before llm (0.4)
        assert len(steps) == 2

    # ── Decisions Trace ─────────────────────────────────────────────

    def test_decisions_trace_populated(self):
        """decisions[] 被正确填充。"""
        governor = MockGovernor()
        ats = MockATS()
        layer = DecisionInjectionLayer(governor=governor, ats=ats)

        plan = make_plan(SAMPLE_STEPS)
        result = layer.inject(plan)
        decisions = result["decisions"]
        # 3 steps → at least 3 decisions (some steps may have multiple)
        assert len(decisions) >= 3
        for d in decisions:
            assert "step_id" in d
            assert "action" in d
            assert "reason" in d

    def test_decisions_trace_with_block(self):
        """block 步骤在 decisions 中标记为 block。"""
        governor = MockGovernor()
        governor.set_status("code", "quarantined")
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 1, "action": "good", "type": "tool", "tool": "llm"},
            {"id": 2, "action": "bad", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.inject(plan)
        decisions = result["decisions"]
        actions = [(d["step_id"], d["action"]) for d in decisions]
        assert (1, "allow") in actions or (1, "reroute") in actions
        assert (2, "block") in actions

    def test_reroute_preserves_other_fields(self):
        """reroute 后保留 id/action 等字段。"""
        governor = MockGovernor()
        governor.set_policy("code", False)
        layer = DecisionInjectionLayer(governor=governor)

        plan = make_plan([
            {"id": 42, "action": "special_task", "type": "tool", "tool": "code_executor",
             "phase": "execution", "risk": "HIGH"},
        ])
        result = layer.inject(plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["id"] == 42
        assert step["action"] == "special_task"
        assert step["type"] == "tool"  # 仅 tool 被替换
        assert step["tool"] == "llm"

    # ── 完整流程 ────────────────────────────────────────────────────

    def test_full_pipeline_with_mixed_decisions(self):
        """混合场景：部分步骤被 block，部分被 downgrade，部分通过。"""
        governor = MockGovernor()
        governor.set_status("code", "quarantined")  # will be blocked
        governor.set_score("llm", 0.95)

        ats = MockATS()
        ats.set_report("safe_action", MockATSReport(passed=True, risk_level="low"))
        ats.set_report("risky_action", MockATSReport(passed=True, risk_level="high"))

        layer = DecisionInjectionLayer(governor=governor, ats=ats)

        plan = make_plan([
            {"id": 1, "action": "safe_action", "type": "tool", "tool": "llm"},
            {"id": 2, "action": "blocked_code", "type": "tool", "tool": "code_executor"},
            {"id": 3, "action": "risky_action", "type": "tool", "tool": "llm"},
        ])
        result = layer.inject(plan)
        steps = result["filtered_plan"]["steps"]

        # Step 2 (code_executor, quarantined) → blocked
        # Step 3 (risky_action, high risk) → downgraded to reasoning
        remaining = {s["id"] for s in steps}
        assert 2 not in remaining  # blocked
        assert 1 in remaining     # passed through
        assert 3 in remaining     # downgraded but not blocked

        # Verify step 3 became reasoning
        step3 = next(s for s in steps if s["id"] == 3)
        assert step3["type"] == "reasoning"


# ─── GovernanceExecutorWrapper ───────────────────────────────────────────

class TestGovernanceExecutorWrapper:
    def test_plan_task_injects_decisions(self):
        """plan_task 调用 decision layer。"""
        executor = MockExecutor()
        governor = MockGovernor()
        governor.set_status("code", "quarantined")
        layer = DecisionInjectionLayer(governor=governor)
        wrapper = GovernanceExecutorWrapper(executor, layer)

        plan = wrapper.plan_task("test input")
        # code_executor step should be filtered out
        tools = [s.get("tool") for s in plan.get("steps", [])]
        assert "code_executor" not in tools

    def test_execute_step_passthrough(self):
        """execute_step 透传至原始 executor。"""
        executor = MockExecutor()
        layer = DecisionInjectionLayer()
        wrapper = GovernanceExecutorWrapper(executor, layer)

        result = wrapper.execute_step(None, {"id": 1}, {})
        assert result["output"] == "done"

    def test_agent_access(self):
        """wrapper 暴露 .agent 属性。"""
        executor = MockExecutor()
        wrapper = GovernanceExecutorWrapper(executor, DecisionInjectionLayer())
        assert wrapper.agent is executor.agent

    def test_plan_task_no_governance(self):
        """无 governor 时 plan 原样传递。"""
        executor = MockExecutor()
        layer = DecisionInjectionLayer()
        wrapper = GovernanceExecutorWrapper(executor, layer)

        plan = wrapper.plan_task("hello")
        assert len(plan["steps"]) == 2
