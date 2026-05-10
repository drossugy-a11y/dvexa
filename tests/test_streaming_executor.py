"""Tests for StreamingExecutorWrapper — 流式执行器包装"""

from __future__ import annotations

from runtime.streaming_executor import StreamingExecutorWrapper
from runtime.step_streamer import StepStreamer
from runtime.step_events import StepType


class _FakeExecutor:
    def __init__(self, plan_steps: int = 2):
        self.plan_called = 0
        self.execute_called = 0
        self._plan_steps = plan_steps

    def plan_task(self, task_input: str) -> dict:
        self.plan_called += 1
        return {
            "goal": "test goal",
            "steps": [
                {"id": i, "action": f"step {i}", "type": "reasoning"}
                for i in range(1, self._plan_steps + 1)
            ],
        }

    def execute_step(self, task: str, step: dict, context: dict) -> dict:
        self.execute_called += 1
        return {"output": f"executed {step.get('action', '?')}", "tool": "llm"}


class TestStreamingExecutorWrapper:

    def setup_method(self):
        self.executor = _FakeExecutor()
        self.streamer = StepStreamer()
        self.wrapper = StreamingExecutorWrapper(self.executor, self.streamer)

    def test_plan_task_delegates(self):
        result = self.wrapper.plan_task("test task")
        assert self.executor.plan_called == 1
        assert result["goal"] == "test goal"

    def test_plan_task_emits_planning_step(self):
        self.wrapper.plan_task("test task")
        steps = self.streamer.get_steps_dict()
        planning_steps = [s for s in steps if s["step_type"] == StepType.PLANNING.value]
        assert len(planning_steps) == 2  # start + finish

    def test_execute_step_delegates(self):
        plan = self.wrapper.plan_task("test")
        step = plan["steps"][0]
        result = self.wrapper.execute_step("task", step, {"total_steps": 2})
        assert self.executor.execute_called == 1
        assert "executed" in result["output"]

    def test_execute_step_emits_execution(self):
        plan = self.wrapper.plan_task("test")
        step = plan["steps"][0]
        self.wrapper.execute_step("task", step, {"total_steps": 2})
        types = {s["step_type"] for s in self.streamer.get_steps_dict()}
        assert StepType.EXECUTION.value in types

    def test_execute_step_with_tool_emits_tool_steps(self):
        plan = self.wrapper.plan_task("test")
        tool_step = {"id": 1, "action": "call api", "type": "tool", "tool": "http_request"}
        self.wrapper.execute_step("task", tool_step, {"total_steps": 2})
        types = {s["step_type"] for s in self.streamer.get_steps_dict()}
        assert StepType.TOOL_CALL.value in types
        assert StepType.TOOL_RESULT.value in types

    def test_execute_step_increments_index(self):
        plan = self.wrapper.plan_task("test")
        steps = plan["steps"]
        self.wrapper.execute_step("task", steps[0], {"total_steps": 3})
        self.wrapper.execute_step("task", steps[1], {"total_steps": 3})
        step_types = [s["step_type"] for s in self.streamer.get_steps_dict()
                      if s["step_type"] == StepType.EXECUTION.value]
        assert len(step_types) == 4  # 1 plan start + 1 plan ready + 2 execute

    def test_plan_task_metadata(self):
        self.wrapper.plan_task("test task")
        steps = self.streamer.get_steps_dict()
        for s in steps:
            if s["step_type"] == StepType.PLANNING.value:
                assert "metadata" in s
                break

    def test_execute_step_without_tool(self):
        plan = self.wrapper.plan_task("test")
        reasoning_step = {"id": 1, "action": "think about this", "type": "reasoning"}
        result = self.wrapper.execute_step("task", reasoning_step, {"total_steps": 1})
        assert result["output"] == "executed think about this"
