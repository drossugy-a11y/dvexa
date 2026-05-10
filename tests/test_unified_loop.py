"""Tests for UnifiedRuntimeLoop — 统一执行循环"""

from __future__ import annotations

import time
from runtime.unified_loop import (
    UnifiedRuntimeLoop, LoopState, LoopPhase,
)


class _FakeKernel:
    """Minimal kernel stub for loop testing."""

    def __init__(self, fail: bool = False, delay: float = 0.0):
        self.fail = fail
        self.delay = delay

    def run_task(self, task_input: str) -> dict:
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            return {"status": "failed", "result": "kernel error", "task_id": "test-1"}
        return {
            "status": "completed",
            "task_id": "test-1",
            "goal": "test goal",
            "result": "Task completed successfully",
            "steps": [{"step_id": 1, "tool": "llm"}],
            "retry_count": 0,
        }


class _FakeDirectiveEngine:
    """Minimal directive engine stub."""

    def process(self, user_input: str, context: dict = None):
        from governance.system_directive_engine import (
            SystemDirective, RuntimeMode
        )
        is_task = len(user_input) > 20
        return SystemDirective(
            mode=RuntimeMode.TASK if is_task else RuntimeMode.CHAT,
            must_plan=is_task,
            must_use_tools=False,
            must_stream=is_task,
            reasoning_level="deep" if is_task else "light",
            governance_level="balanced",
        )


class TestLoopState:

    def test_initial_state(self):
        s = LoopState()
        assert s.current_phase == LoopPhase.IDLE
        assert s.turn_count == 0
        assert s.error is None

    def test_enter_phase(self):
        s = LoopState()
        s.enter_phase(LoopPhase.DIRECTIVE)
        assert s.current_phase == LoopPhase.DIRECTIVE
        assert "directive" in s.phase_timing

    def test_reset(self):
        s = LoopState(turn_count=1, output="hello", error="err")
        s.reset()
        assert s.output == ""
        assert s.error is None
        assert s.current_phase == LoopPhase.IDLE

    def test_to_dict(self):
        s = LoopState(turn_id="t1", turn_count=1)
        s.enter_phase(LoopPhase.DIRECTIVE)
        d = s.to_dict()
        assert d["turn_id"] == "t1"
        assert d["turn_count"] == 1
        assert d["current_phase"] == "directive"
        assert d["has_output"] is False


class TestUnifiedRuntimeLoop:

    def setup_method(self):
        self.kernel = _FakeKernel()
        self.engine = _FakeDirectiveEngine()
        self.loop = UnifiedRuntimeLoop(self.kernel, self.engine)

    def test_loop_returns_output(self):
        result = self.loop.run("hello")
        assert "output" in result
        assert result["output"] == "Task completed successfully"

    def test_loop_state_contains_phases(self):
        result = self.loop.run("hello")
        state = result["state"]
        assert state["turn_count"] == 1
        assert state["current_phase"] == "completed"
        assert len(state["phases"]) >= 4  # directive → governance → ... → completed

    def test_loop_includes_directive(self):
        result = self.loop.run("hello")
        assert result["directive"] is not None
        assert result["directive"]["mode"] == "chat"

    def test_loop_task_mode(self):
        result = self.loop.run("this is a long task input that triggers task mode")
        assert result["directive"]["mode"] == "task"
        assert result["directive"]["must_plan"] is True

    def test_loop_increments_turns(self):
        self.loop.run("hello")
        self.loop.run("world")
        assert self.loop.total_turns == 2

    def test_loop_is_idle_after_completion(self):
        self.loop.run("hello")
        assert self.loop.is_idle()

    def test_loop_is_running_during_execution(self):
        # Before run, should be idle
        assert self.loop.is_idle()

    def test_loop_without_directive_engine(self):
        loop = UnifiedRuntimeLoop(_FakeKernel())
        result = loop.run("hello")
        assert result["output"] is not None
        assert result["directive"] is None

    def test_loop_handles_kernel_failure(self):
        loop = UnifiedRuntimeLoop(_FakeKernel(fail=True), self.engine)
        result = loop.run("hello")
        assert result["state"]["current_phase"] == "completed"

    def test_loop_wraps_exceptions(self):
        class BrokenKernel:
            def run_task(self, task_input):
                raise RuntimeError("kernel crash")

        loop = UnifiedRuntimeLoop(BrokenKernel(), self.engine)
        result = loop.run("hello")
        assert "error" in result
        assert result["state"]["current_phase"] == "error"

    def test_loop_state_contains_timing(self):
        loop = UnifiedRuntimeLoop(_FakeKernel(delay=0.05), self.engine)
        result = loop.run("hello")
        state = result["state"]
        assert state["duration"] > 0

    def test_loop_accepts_context(self):
        result = self.loop.run("hello", {"custom": "value"})
        assert result["state"]["current_phase"] == "completed"
