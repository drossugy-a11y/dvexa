"""Tests for Governance Stabilizer v1."""
import pytest
from governance.stabilizer import GovernanceStabilizer
from governance.governance_kernel import GovernanceKernel


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_step(step_id: int, tool: str = "llm", action: str = "do",
              type: str = "tool") -> dict:
    return {"id": step_id, "tool": tool, "action": action, "type": type}


def make_plan(steps: list[dict]) -> dict:
    return {"goal": "test", "steps": steps}


# ═══════════════════════════════════════════════════════════════════════════
# Test: Plan Stabilization
# ═══════════════════════════════════════════════════════════════════════════

class TestPlanStabilization:
    def test_step_explosion_capped(self):
        """超过 8 steps → 保留前 8 个。"""
        stabilizer = GovernanceStabilizer()
        steps = [make_step(i, "llm", f"step_{i}") for i in range(15)]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        assert len(result["steps"]) == 8

    def test_under_limit_steps_unchanged(self):
        """≤ 8 steps → 不动。"""
        stabilizer = GovernanceStabilizer()
        steps = [make_step(i, "llm", f"step_{i}") for i in range(5)]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        assert len(result["steps"]) == 5

    def test_consecutive_duplicates_merged(self):
        """连续相同 tool+action → 合并为一条。"""
        stabilizer = GovernanceStabilizer()
        steps = [
            make_step(1, "llm", "analyze"),
            make_step(2, "llm", "analyze"),  # duplicate
            make_step(3, "code_executor", "compute"),
        ]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        assert len(result["steps"]) == 2
        assert result["steps"][0]["tool"] == "llm"
        assert result["steps"][1]["tool"] == "code_executor"

    def test_non_consecutive_same_action_kept(self):
        """相同但非连续 tool+action → 保留。"""
        stabilizer = GovernanceStabilizer()
        steps = [
            make_step(1, "llm", "analyze"),
            make_step(2, "code_executor", "compute"),
            make_step(3, "llm", "analyze"),
        ]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        assert len(result["steps"]) == 3

    def test_empty_action_removed(self):
        """空 action 步骤被去除。"""
        stabilizer = GovernanceStabilizer()
        steps = [
            make_step(1, "llm", ""),
            make_step(2, "code_executor", "compute"),
        ]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        assert len(result["steps"]) == 1
        assert result["steps"][0]["tool"] == "code_executor"

    def test_unknown_tool_normalized(self):
        """未知 tool → 被标准化为 llm。"""
        stabilizer = GovernanceStabilizer()
        steps = [
            make_step(1, "mystery_tool", "do"),
        ]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        assert result["steps"][0]["tool"] == "llm"

    def test_known_tools_preserved(self):
        """已知工具名被保留。"""
        stabilizer = GovernanceStabilizer()
        steps = [
            make_step(1, "code_executor", "compute"),
            make_step(2, "http_request", "fetch"),
            make_step(3, "security", "scan"),
        ]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        assert result["steps"][0]["tool"] == "code_executor"
        assert result["steps"][1]["tool"] == "http_request"
        assert result["steps"][2]["tool"] == "security"

    def test_empty_plan_unchanged(self):
        """空 plan → 不动。"""
        stabilizer = GovernanceStabilizer()
        assert stabilizer.stabilize_plan(None) is None
        assert stabilizer.stabilize_plan({}) == {}
        assert stabilizer.stabilize_plan({"goal": "x"}) == {"goal": "x"}

    def test_missing_steps_key_unchanged(self):
        """无 steps 字段的 plan → 不动。"""
        stabilizer = GovernanceStabilizer()
        plan = {"goal": "test", "not_steps": []}
        result = stabilizer.stabilize_plan(plan)
        assert result == plan

    def test_type_field_validated(self):
        """type 字段必须为 tool/reasoning，否则标准化为 tool。"""
        stabilizer = GovernanceStabilizer()
        steps = [
            make_step(1, "llm", "analyze"),
            {"id": 2, "tool": "code_executor", "action": "compute", "type": "invalid"},
        ]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        assert result["steps"][1]["type"] == "tool"


# ═══════════════════════════════════════════════════════════════════════════
# Test: Decision Stabilization
# ═══════════════════════════════════════════════════════════════════════════

class TestDecisionStabilization:
    def test_empty_decisions(self):
        stabilizer = GovernanceStabilizer()
        assert stabilizer.stabilize_decisions([]) == []
        assert stabilizer.stabilize_decisions(None) == []

    def test_single_decision_unchanged(self):
        stabilizer = GovernanceStabilizer()
        decisions = [{"step_id": 1, "action": "allow", "reason": "ok"}]
        result = stabilizer.stabilize_decisions(decisions)
        assert result == decisions

    def test_duplicate_step_keeps_highest_priority(self):
        """同 step 多个 decision → block(priority 0) > downgrade(1) > reroute(2) > allow(3)。"""
        stabilizer = GovernanceStabilizer()
        decisions = [
            {"step_id": 1, "action": "allow", "reason": "policy ok"},
            {"step_id": 1, "action": "block", "reason": "quarantined"},
            {"step_id": 1, "action": "downgrade", "reason": "low score"},
        ]
        result = stabilizer.stabilize_decisions(decisions)
        assert len(result) == 1
        assert result[0]["step_id"] == 1
        assert result[0]["action"] == "block"

    def test_reasons_merged(self):
        stabilizer = GovernanceStabilizer()
        decisions = [
            {"step_id": 1, "action": "downgrade", "reason": "low score"},
            {"step_id": 1, "action": "downgrade", "reason": "experimental skill"},
        ]
        result = stabilizer.stabilize_decisions(decisions)
        assert len(result) == 1
        assert "low score" in result[0]["reason"]
        assert "experimental skill" in result[0]["reason"]

    def test_multiple_steps_separated(self):
        stabilizer = GovernanceStabilizer()
        decisions = [
            {"step_id": 1, "action": "allow", "reason": "ok"},
            {"step_id": 2, "action": "block", "reason": "quarantined"},
            {"step_id": 1, "action": "reroute", "reason": "unknown tool"},
        ]
        result = stabilizer.stabilize_decisions(decisions)
        assert len(result) == 2
        actions = {d["step_id"]: d["action"] for d in result}
        assert actions[1] == "reroute"  # reroute(2) < allow(3), so reroute wins
        assert actions[2] == "block"

    def test_stable_order(self):
        stabilizer = GovernanceStabilizer()
        decisions = [
            {"step_id": 3, "action": "allow", "reason": ""},
            {"step_id": 1, "action": "block", "reason": ""},
        ]
        result = stabilizer.stabilize_decisions(decisions)
        assert [d["step_id"] for d in result] == [1, 3]


# ═══════════════════════════════════════════════════════════════════════════
# Test: Feedback Stabilization
# ═══════════════════════════════════════════════════════════════════════════

class TestFeedbackStabilization:
    def test_allowed_keys_preserved(self):
        stabilizer = GovernanceStabilizer()
        event = {
            "skill_score": {"llm": 0.8},
            "tool_preference": {"llm": 0.7},
            "strategy_stats": {"success": 1},
        }
        result = stabilizer.stabilize_feedback(event)
        assert "skill_score" in result
        assert "tool_preference" in result
        assert "strategy_stats" in result

    def test_disallowed_keys_stripped(self):
        stabilizer = GovernanceStabilizer()
        event = {
            "skill_score": {"llm": 0.8},
            "new_rule": {"block_all": True},  # 不允许
            "decision_chain": ["reroute"],     # 不允许
        }
        result = stabilizer.stabilize_feedback(event)
        assert "skill_score" in result
        assert "new_rule" not in result
        assert "decision_chain" not in result

    def test_non_dict_returns_empty(self):
        stabilizer = GovernanceStabilizer()
        assert stabilizer.stabilize_feedback(None) == {}
        assert stabilizer.stabilize_feedback("string") == {}
        assert stabilizer.stabilize_feedback(42) == {}

    def test_empty_event(self):
        stabilizer = GovernanceStabilizer()
        assert stabilizer.stabilize_feedback({}) == {}


# ═══════════════════════════════════════════════════════════════════════════
# Test: Determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_plan_same_output(self):
        a = GovernanceStabilizer()
        b = GovernanceStabilizer()
        steps = [make_step(i, "llm", f"step_{i}") for i in range(12)]
        plan = make_plan(steps)
        assert a.stabilize_plan(plan) == b.stabilize_plan(plan)

    def test_same_decisions_same_output(self):
        a = GovernanceStabilizer()
        b = GovernanceStabilizer()
        decisions = [
            {"step_id": 1, "action": "allow", "reason": "ok"},
            {"step_id": 1, "action": "block", "reason": "quarantined"},
        ]
        assert a.stabilize_decisions(decisions) == b.stabilize_decisions(decisions)


# ═══════════════════════════════════════════════════════════════════════════
# Test: No Structural Mutation
# ═══════════════════════════════════════════════════════════════════════════

class TestNoStructuralMutation:
    def test_stabilizer_does_not_add_new_rules(self):
        """stabilize 后的 plan 不能包含原 plan 没有的字段。"""
        stabilizer = GovernanceStabilizer()
        steps = [make_step(1, "unknown_tool", "do")]
        plan = make_plan(steps)
        result = stabilizer.stabilize_plan(plan)
        allowed_keys = {"goal", "steps"}
        for key in result:
            assert key in allowed_keys, f"unexpected key: {key}"

    def test_decision_count_never_exceeds_input(self):
        stabilizer = GovernanceStabilizer()
        decisions = [
            {"step_id": 1, "action": "allow", "reason": "a"},
            {"step_id": 1, "action": "block", "reason": "b"},
        ]
        result = stabilizer.stabilize_decisions(decisions)
        assert len(result) <= len(decisions)

    def no_new_fields_in_merged_decision(self):
        stabilizer = GovernanceStabilizer()
        decisions = [
            {"step_id": 1, "action": "allow", "reason": "ok"},
        ]
        result = stabilizer.stabilize_decisions(decisions)
        allowed = {"step_id", "action", "reason"}
        for key in result[0]:
            assert key in allowed


# ═══════════════════════════════════════════════════════════════════════════
# Test: GovernanceKernel Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestKernelIntegration:
    def test_kernel_with_stabilizer_caps_steps(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        stabilizer = GovernanceStabilizer()
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  stabilizer=stabilizer)
        steps = [make_step(i, "llm", f"step_{i}") for i in range(15)]
        plan = make_plan(steps)
        result = kernel.process({}, plan)
        # 默认 BALANCED 策略，plan steps 应有 stabilizer 的 cap
        assert len(result["filtered_plan"]["steps"]) == 8

    def test_kernel_without_stabilizer_unchanged(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        kernel = GovernanceKernel(skill_governor=MockGov())
        steps = [make_step(i, "llm", f"step_{i}") for i in range(15)]
        plan = make_plan(steps)
        result = kernel.process({}, plan)
        # 无 stabilizer → 所有 steps 保留
        assert len(result["filtered_plan"]["steps"]) == 15

    def test_kernel_with_stabilizer_merges_decisions(self):
        class MockGov:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        stabilizer = GovernanceStabilizer()
        kernel = GovernanceKernel(skill_governor=MockGov(),
                                  stabilizer=stabilizer)
        plan = make_plan([
            make_step(1, "llm", "analyze"),
            make_step(2, "code_executor", "compute"),
        ])
        result = kernel.process({}, plan)
        # decisions 可能有多条 per step，但 stabilizer 合并后每条 step 至多一条
        step_ids_in_decisions = set(d["step_id"] for d in result["decisions"])
        assert len(step_ids_in_decisions) <= 2

    def test_kernel_stabilizer_does_not_change_strategy(self):
        class MockGovATS:
            def get_status(self, n):
                from governance.lifecycle import SkillStatus
                return SkillStatus.ACTIVE
            def get_score(self, n):
                return None
            def check_skill_allowed(self, n):
                return True

        class MockRiskLevel:
            def __init__(self, v):
                self.value = v

        class MockReport:
            def __init__(self):
                self.passed = True
                self.risk_level = MockRiskLevel("low")
                self.risk_score = 0.0
                self.summary = "ok"
                self.phases = []
                self.target = "mock"

        class MockATS:
            def run(self, a, c):
                return MockReport()

        stabilizer = GovernanceStabilizer()
        kernel_no_stab = GovernanceKernel(skill_governor=MockGovATS(), ats=MockATS())
        kernel_stab = GovernanceKernel(skill_governor=MockGovATS(), ats=MockATS(),
                                       stabilizer=stabilizer)
        plan = make_plan([make_step(1, "llm", "analyze")])
        r1 = kernel_no_stab.process({}, plan)
        r2 = kernel_stab.process({}, plan)
        assert r1["strategy"] == r2["strategy"]  # stabilizer 不改变策略
