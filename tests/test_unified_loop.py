"""Tests for UnifiedRuntimeLoop — 统一执行循环"""

from __future__ import annotations

import time
from runtime.unified_loop import UnifiedRuntimeLoop
from runtime.runtime_state_machine import RuntimeStateMachine


class _FakeKernel:
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
    def process(self, user_input: str, context: dict = None):
        from governance.system_directive_engine import SystemDirective, RuntimeMode
        is_task = len(user_input) > 20
        return SystemDirective(
            mode=RuntimeMode.TASK if is_task else RuntimeMode.CHAT,
            must_plan=is_task, must_use_tools=False,
            must_stream=is_task,
            reasoning_level="deep" if is_task else "light",
            governance_level="balanced",
        )


class TestUnifiedRuntimeLoop:

    def setup_method(self):
        self.kernel = _FakeKernel()
        self.engine = _FakeDirectiveEngine()
        self.sm = RuntimeStateMachine()
        self.loop = UnifiedRuntimeLoop(self.kernel, self.engine,
                                       state_machine=self.sm)

    def test_loop_returns_output(self):
        result = self.loop.run("hello")
        assert "output" in result
        assert result["output"] == "Task completed successfully"

    def test_loop_uses_state_machine(self):
        self.loop.run("hello")
        assert self.sm.get_state().value == "idle"
        assert len(self.sm.history) > 5

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

    def test_loop_without_directive_engine(self):
        loop = UnifiedRuntimeLoop(_FakeKernel(), state_machine=RuntimeStateMachine())
        result = loop.run("hello")
        assert result["output"] is not None

    def test_loop_handles_kernel_failure(self):
        loop = UnifiedRuntimeLoop(
            _FakeKernel(fail=True), self.engine,
            state_machine=RuntimeStateMachine(),
        )
        result = loop.run("hello")
        # Failed kernel returns error text in output
        assert "error" in result["output"].lower() or "kernel error" in result["output"]

    def test_loop_state_tracks_phases(self):
        result = self.loop.run("hello")
        turn = result["turn"]
        assert turn["phases"] is not None
        assert "directive" in turn["phases"]

    def test_loop_state_machine_accessible(self):
        assert self.loop.state_machine is self.sm

    def test_state_machine_tracks_entire_run(self):
        sm = RuntimeStateMachine()
        loop = UnifiedRuntimeLoop(_FakeKernel(), state_machine=sm)
        loop.run("test")
        # Should have gone through multiple states
        states = {e.to_state.value for e in sm.history}
        assert "input_received" in states
        assert "completed" in states or "idle" in states
