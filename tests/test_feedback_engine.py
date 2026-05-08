"""Tests for Governance Feedback Engine v1."""
import pytest
from governance.feedback_engine import GovernanceFeedbackEngine
from core.kernel import DVexaKernel


# ─── Mock Objects ────────────────────────────────────────────────────────────

class MockGovernor:
    """Mock SkillGovernor 追踪 record_call 调用。"""

    def __init__(self):
        self.calls: list[dict] = []

    def record_call(self, name: str, success: bool = True,
                    latency: float = 0.0, error: str = ""):
        self.calls.append({
            "name": name,
            "success": success,
            "latency": latency,
            "error": error,
        })

    def get_score(self, name: str):
        return None


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_trace(strategy: str = "BALANCED", steps: list[dict] | None = None,
               task: str = "test") -> dict:
    return {
        "task": task,
        "strategy_used": strategy,
        "steps": steps or [],
    }


def make_step(step_id: int = 1, tool: str = "llm", action: str = "test",
              success: bool = True, latency: float = 0.5) -> dict:
    return {
        "step_id": step_id,
        "tool": tool,
        "action": action,
        "success": success,
        "latency": latency,
    }


def make_outcome(status: str = "success", error_type: str = "",
                 total_latency: float = 1.0) -> dict:
    return {
        "status": status,
        "error_type": error_type,
        "total_latency": total_latency,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Test: Basic Recording
# ═══════════════════════════════════════════════════════════════════════════

class TestBasicRecording:
    def test_record_success_updates_governor(self):
        governor = MockGovernor()
        engine = GovernanceFeedbackEngine(skill_governor=governor)
        engine.record_execution(
            make_trace(steps=[make_step()]),
            make_outcome(status="success"),
        )
        assert len(governor.calls) == 1
        assert governor.calls[0]["name"] == "llm"
        assert governor.calls[0]["success"] is True
        assert governor.calls[0]["latency"] == 0.5

    def test_record_failure_updates_governor(self):
        governor = MockGovernor()
        engine = GovernanceFeedbackEngine(skill_governor=governor)
        engine.record_execution(
            make_trace(steps=[make_step(success=False)]),
            make_outcome(status="fail"),
        )
        assert len(governor.calls) == 1
        assert governor.calls[0]["success"] is False
        assert "error" in governor.calls[0]

    def test_multiple_steps_all_recorded(self):
        governor = MockGovernor()
        engine = GovernanceFeedbackEngine(skill_governor=governor)
        engine.record_execution(
            make_trace(steps=[
                make_step(step_id=1, tool="llm", success=True),
                make_step(step_id=2, tool="code_executor", success=False),
                make_step(step_id=3, tool="http_request", success=True),
            ]),
            make_outcome(status="fail"),
        )
        assert len(governor.calls) == 3
        assert governor.calls[0]["name"] == "llm"
        assert governor.calls[1]["name"] == "code_executor"
        assert governor.calls[1]["success"] is False
        assert governor.calls[2]["name"] == "http_request"

    def test_no_governor_does_not_crash(self):
        engine = GovernanceFeedbackEngine()
        result = engine.record_execution(
            make_trace(steps=[make_step()]),
            make_outcome(),
        )
        assert result is None

    def test_empty_trace_does_not_crash(self):
        governor = MockGovernor()
        engine = GovernanceFeedbackEngine(skill_governor=governor)
        engine.record_execution(make_trace(steps=[]), make_outcome())
        assert len(governor.calls) == 0

    def test_step_without_tool_skipped(self):
        governor = MockGovernor()
        engine = GovernanceFeedbackEngine(skill_governor=governor)
        engine.record_execution(
            make_trace(steps=[{"step_id": 1, "action": "test",
                               "success": True, "latency": 0.0}]),
            make_outcome(),
        )
        assert len(governor.calls) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Test: Tool Preference Adaptation
# ═══════════════════════════════════════════════════════════════════════════

class TestToolPreferenceAdaptation:
    def test_default_preference_is_0_5(self):
        engine = GovernanceFeedbackEngine()
        assert engine.get_preference("llm") == 0.5

    def test_consecutive_success_increases_preference(self):
        engine = GovernanceFeedbackEngine(alpha=0.1, beta=0.15)
        for _ in range(6):  # threshold=5
            engine.record_execution(
                make_trace(steps=[make_step(tool="llm")]),
                make_outcome(status="success"),
            )
        pref = engine.get_preference("llm")
        assert pref > 0.5

    def test_consecutive_failures_decreases_preference(self):
        engine = GovernanceFeedbackEngine(alpha=0.1, beta=0.15)
        for _ in range(4):  # threshold=3
            engine.record_execution(
                make_trace(steps=[make_step(tool="llm", success=False)]),
                make_outcome(status="fail"),
            )
        pref = engine.get_preference("llm")
        assert pref < 0.5

    def test_mixed_outcomes_no_change(self):
        engine = GovernanceFeedbackEngine(alpha=0.1, beta=0.15)
        # success, fail, success, fail — 未达到连续阈值
        for success in [True, False, True, False]:
            engine.record_execution(
                make_trace(steps=[make_step(tool="llm", success=success)]),
                make_outcome(status="success" if success else "fail"),
            )
        # 默认 0.5，未发生调整
        assert engine.get_preference("llm") == 0.5

    def test_preference_clamped(self):
        engine = GovernanceFeedbackEngine(alpha=0.5, beta=0.5)
        # 多次成功应 clamp 在 0.95
        for _ in range(100):
            engine.record_execution(
                make_trace(steps=[make_step(tool="llm")]),
                make_outcome(status="success"),
            )
        assert engine.get_preference("llm") <= 0.95

        # 多次失败应 clamp 在 0.05
        for _ in range(100):
            engine.record_execution(
                make_trace(steps=[make_step(tool="code_executor", success=False)]),
                make_outcome(status="fail"),
            )
        assert engine.get_preference("code_executor") >= 0.05

    def test_different_tools_independent(self):
        engine = GovernanceFeedbackEngine(alpha=0.1, beta=0.15)
        for _ in range(6):
            engine.record_execution(
                make_trace(steps=[make_step(tool="llm")]),
                make_outcome(status="success"),
            )
        for _ in range(4):
            engine.record_execution(
                make_trace(steps=[make_step(tool="code_executor", success=False)]),
                make_outcome(status="fail"),
            )
        assert engine.get_preference("llm") > 0.5
        assert engine.get_preference("code_executor") < 0.5


# ═══════════════════════════════════════════════════════════════════════════
# Test: Strategy Statistics
# ═══════════════════════════════════════════════════════════════════════════

class TestStrategyStatistics:
    def test_strategy_stats_empty_initially(self):
        engine = GovernanceFeedbackEngine()
        assert engine.get_strategy_stats() == {}

    def test_strategy_success_increments(self):
        stats: dict = {}
        engine = GovernanceFeedbackEngine(strategy_stats=stats)
        engine.record_execution(
            make_trace(strategy="BALANCED"),
            make_outcome(status="success"),
        )
        assert stats["BALANCED"]["success"] == 1
        assert stats["BALANCED"]["total"] == 1

    def test_strategy_fail_increments(self):
        stats: dict = {}
        engine = GovernanceFeedbackEngine(strategy_stats=stats)
        engine.record_execution(
            make_trace(strategy="STRICT"),
            make_outcome(status="fail"),
        )
        assert stats["STRICT"]["fail"] == 1
        assert stats["STRICT"]["total"] == 1

    def test_success_rate_computed(self):
        stats: dict = {}
        engine = GovernanceFeedbackEngine(strategy_stats=stats)
        for _ in range(3):
            engine.record_execution(
                make_trace(strategy="BALANCED"),
                make_outcome(status="success"),
            )
        engine.record_execution(
            make_trace(strategy="BALANCED"),
            make_outcome(status="fail"),
        )
        assert stats["BALANCED"]["success"] == 3
        assert stats["BALANCED"]["fail"] == 1
        assert stats["BALANCED"]["total"] == 4
        assert stats["BALANCED"]["success_rate"] == 0.75

    def test_multiple_strategies_tracked(self):
        stats: dict = {}
        engine = GovernanceFeedbackEngine(strategy_stats=stats)
        for _ in range(5):
            engine.record_execution(
                make_trace(strategy="BALANCED"),
                make_outcome(status="success"),
            )
        for _ in range(3):
            engine.record_execution(
                make_trace(strategy="STRICT"),
                make_outcome(status="fail"),
            )
        assert stats["BALANCED"]["success"] == 5
        assert stats["STRICT"]["fail"] == 3
        assert stats["STRICT"]["success_rate"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Test: ATS Drift Detection
# ═══════════════════════════════════════════════════════════════════════════

class TestATSDriftDetection:
    def test_no_drift_on_success(self):
        engine = GovernanceFeedbackEngine()
        engine.record_execution(
            make_trace(steps=[make_step(success=True)]),
            make_outcome(status="success"),
        )
        assert engine.get_ats_drift_signals() == []

    def test_no_drift_on_fail_without_enough_steps(self):
        engine = GovernanceFeedbackEngine()
        engine.record_execution(
            make_trace(steps=[make_step(success=True)]),
            make_outcome(status="fail"),
        )
        # 只有 1 step，不到 3 个 approved
        assert engine.get_ats_drift_signals() == []

    def test_drift_on_high_fail_rate_among_approved(self):
        engine = GovernanceFeedbackEngine()
        engine.record_execution(
            make_trace(steps=[
                make_step(step_id=1, tool="llm", success=False),
                make_step(step_id=2, tool="code", success=False),
                make_step(step_id=3, tool="http", success=True),
            ]),
            make_outcome(status="fail"),
        )
        signals = engine.get_ats_drift_signals()
        # 3 approved steps, 2 failed → 66.7% > 30% → drift
        assert len(signals) == 1
        assert signals[0]["type"] == "ats_threshold_drift"


# ═══════════════════════════════════════════════════════════════════════════
# Test: Determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_input_same_preference(self):
        engine_a = GovernanceFeedbackEngine(alpha=0.1, beta=0.15)
        engine_b = GovernanceFeedbackEngine(alpha=0.1, beta=0.15)

        trace = make_trace(steps=[
            make_step(tool="llm", success=True),
            make_step(tool="code_executor", success=False),
        ])
        outcome = make_outcome(status="fail")

        for _ in range(3):
            engine_a.record_execution(trace, outcome)
            engine_b.record_execution(trace, outcome)

        assert engine_a.get_preference("llm") == engine_b.get_preference("llm")
        assert engine_a.get_preference("code_executor") == engine_b.get_preference("code_executor")

    def test_same_input_same_strategy_stats(self):
        stats_a: dict = {}
        stats_b: dict = {}
        engine_a = GovernanceFeedbackEngine(strategy_stats=stats_a)
        engine_b = GovernanceFeedbackEngine(strategy_stats=stats_b)

        trace = make_trace(strategy="BALANCED")
        outcome_s = make_outcome(status="success")
        outcome_f = make_outcome(status="fail")

        for _ in range(3):
            engine_a.record_execution(trace, outcome_s)
            engine_b.record_execution(trace, outcome_s)
        engine_a.record_execution(trace, outcome_f)
        engine_b.record_execution(trace, outcome_f)

        assert stats_a == stats_b


# ═══════════════════════════════════════════════════════════════════════════
# Test: Debug Snapshot
# ═══════════════════════════════════════════════════════════════════════════

class TestDebugSnapshot:
    def test_snapshot_contains_all_fields(self):
        engine = GovernanceFeedbackEngine()
        snapshot = engine.get_debug_snapshot()
        assert "preferences" in snapshot
        assert "strategy_stats" in snapshot
        assert "ats_drift_signals" in snapshot
        assert "total_executions" in snapshot

    def test_snapshot_reflects_updates(self):
        engine = GovernanceFeedbackEngine(alpha=0.1, beta=0.15)
        for _ in range(6):
            engine.record_execution(
                make_trace(steps=[make_step(tool="llm")]),
                make_outcome(status="success"),
            )
        snapshot = engine.get_debug_snapshot()
        assert snapshot["total_executions"] == 6


# ═══════════════════════════════════════════════════════════════════════════
# Test: Append-Only History
# ═══════════════════════════════════════════════════════════════════════════

class TestAppendOnlyHistory:
    def test_history_increments(self):
        engine = GovernanceFeedbackEngine()
        assert len(engine.get_history()) == 0
        engine.record_execution(make_trace(), make_outcome())
        assert len(engine.get_history()) == 1
        engine.record_execution(make_trace(), make_outcome())
        assert len(engine.get_history()) == 2

    def test_history_contains_trace_and_outcome(self):
        engine = GovernanceFeedbackEngine()
        trace = make_trace(strategy="STRICT", task="test123")
        outcome = make_outcome(status="fail")
        engine.record_execution(trace, outcome)
        entry = engine.get_history()[0]
        assert entry["trace"]["task"] == "test123"
        assert entry["trace"]["strategy_used"] == "STRICT"
        assert entry["outcome"]["status"] == "fail"

    def test_history_is_copy_not_reference(self):
        engine = GovernanceFeedbackEngine()
        engine.record_execution(make_trace(), make_outcome())
        history = engine.get_history()
        history.clear()
        assert len(engine.get_history()) == 1  # original unaffected


# ═══════════════════════════════════════════════════════════════════════════
# Test: Edge Cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_record_without_strategy(self):
        governor = MockGovernor()
        engine = GovernanceFeedbackEngine(skill_governor=governor)
        engine.record_execution(
            {"task": "no_strategy", "steps": [make_step()]},
            make_outcome(status="success"),
        )
        # 不崩溃即可
        assert True

    def test_strategy_stats_mutates_passed_dict(self):
        stats: dict = {}
        engine = GovernanceFeedbackEngine(strategy_stats=stats)
        engine.record_execution(
            make_trace(strategy="BALANCED"),
            make_outcome(status="success"),
        )
        assert "BALANCED" in stats  # 外部 dict 被修改

    def test_repeated_execution_safe(self):
        engine = GovernanceFeedbackEngine(alpha=0.1, beta=0.15)
        trace = make_trace(steps=[make_step(tool="llm", success=True)])
        outcome = make_outcome(status="success")
        for _ in range(100):
            engine.record_execution(trace, outcome)
        # 不崩溃，preference 被 clamp
        assert 0.0 <= engine.get_preference("llm") <= 1.0

    def test_default_parameters(self):
        engine = GovernanceFeedbackEngine()
        assert engine.alpha == 0.1
        assert engine.beta == 0.15


# ═══════════════════════════════════════════════════════════════════════════
# Test: Kernel Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestKernelIntegration:
    def test_kernel_with_feedback_engine(self):
        """验证 kernel 接受 feedback_engine 不崩溃。"""
        from core.state import TaskState, TaskStatus

        class MockScheduler:
            def create_task(self, inp):
                return TaskState(inp)

        class MockExecutor:
            def plan_task(self, inp):
                return {"goal": "test", "steps": [
                    {"id": 1, "action": "test", "type": "tool", "tool": "llm"},
                ]}

            def execute_step(self, task, step, ctx):
                task.add_step_record({"step_id": 1, "tool": "llm", "action": "test",
                                       "tool_output": "ok"})
                return {"step_id": 1, "output": "ok"}

        class MockMemory:
            def save(self, task):
                pass

        governor = MockGovernor()
        stats: dict = {}
        engine = GovernanceFeedbackEngine(skill_governor=governor,
                                           strategy_stats=stats)
        kernel = DVexaKernel(MockScheduler(), MockExecutor(), MockMemory(),
                              feedback_engine=engine)
        result = kernel.run_task("hello")
        assert result["status"] == "completed"
        # 验证反馈引擎的 governor 被调用了
        assert len(governor.calls) > 0

    def test_kernel_without_feedback_engine(self):
        """无 feedback_engine 时正常运行。"""
        from core.state import TaskState

        class MockScheduler:
            def create_task(self, inp):
                return TaskState(inp)

        class MockExecutor:
            def plan_task(self, inp):
                return {"goal": "test", "steps": [{"id": 1, "action": "t",
                                                     "type": "tool", "tool": "llm"}]}

            def execute_step(self, task, step, ctx):
                task.add_step_record({"step_id": 1, "tool": "llm", "action": "t"})
                return {"step_id": 1, "output": "ok"}

        class MockMemory:
            def save(self, task):
                pass

        kernel = DVexaKernel(MockScheduler(), MockExecutor(), MockMemory())
        result = kernel.run_task("hello")
        assert result["status"] == "completed"
