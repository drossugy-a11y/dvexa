"""Tests for StepStreamer v1 — 流式执行步骤"""

from runtime.step_events import StepType, RuntimeStep, make_step
from runtime.step_streamer import StepStreamer
from runtime.runtime_state_machine import RuntimeStateMachine, RuntimeState


class TestRuntimeStep:

    def test_make_step(self):
        step = make_step(StepType.PLANNING, "Planning", "content")
        assert step.step_type == StepType.PLANNING
        assert step.title == "Planning"
        assert step.content == "content"
        assert step.step_id != ""
        assert step.timestamp > 0

    def test_step_to_dict(self):
        step = make_step(StepType.EXECUTION, "Exec", "doing work",
                         runtime_state="executing")
        d = step.to_dict()
        assert d["event_type"] == "runtime_step"
        assert d["step_type"] == "execution"
        assert d["runtime_state"] == "executing"

    def test_step_type_values(self):
        assert StepType.DIRECTIVE.value == "directive"
        assert StepType.GOVERNANCE.value == "governance"
        assert StepType.TOOL_CALL.value == "tool_call"
        assert StepType.TOOL_RESULT.value == "tool_result"
        assert StepType.COMPLETE.value == "complete"


class TestStepStreamer:

    def setup_method(self):
        self.sm = RuntimeStateMachine()
        self.streamer = StepStreamer(self.sm)

    def test_emit_adds_step(self):
        self.streamer.emit(StepType.PLANNING, "Test", "content")
        assert self.streamer.step_count == 1

    def test_emit_order(self):
        self.streamer.planning("first")
        self.streamer.execution("second")
        self.streamer.complete("third")
        assert self.streamer.steps[0].step_type == StepType.PLANNING
        assert self.streamer.steps[1].step_type == StepType.EXECUTION
        assert self.streamer.steps[2].step_type == StepType.COMPLETE

    def test_convenience_methods(self):
        self.streamer.directive("d")
        self.streamer.governance("g")
        self.streamer.planning("p")
        self.streamer.execution("e")
        self.streamer.tool_call("tc")
        self.streamer.tool_result("tr")
        self.streamer.thinking("t")
        self.streamer.memory("m")
        self.streamer.output("o")
        self.streamer.complete("c")
        assert self.streamer.step_count == 10

    def test_error_step(self):
        self.streamer.error("Something broke", "error details")
        assert self.streamer.steps[0].step_type == StepType.ERROR

    def test_blocked_step(self):
        self.streamer.blocked("policy violation")
        assert self.streamer.steps[0].step_type == StepType.BLOCKED

    def test_ws_push_called(self):
        pushed = []

        def ws(data):
            pushed.append(data)

        streamer = StepStreamer(ws_push=ws)
        streamer.planning("test")
        assert len(pushed) == 1
        assert pushed[0]["step_type"] == "planning"

    def test_observer_notified(self):
        received = []

        def obs(step):
            received.append(step)

        self.streamer.subscribe(obs)
        self.streamer.execution("test")
        assert len(received) == 1
        assert received[0].step_type == StepType.EXECUTION

    def test_unsubscribe(self):
        received = []

        def obs(step):
            received.append(step)

        self.streamer.subscribe(obs)
        self.streamer.unsubscribe(obs)
        self.streamer.execution("test")
        assert len(received) == 0

    def test_clear(self):
        self.streamer.planning("test")
        assert self.streamer.step_count == 1
        self.streamer.clear()
        assert self.streamer.step_count == 0

    def test_runtime_state_in_step(self):
        self.sm.start_turn("t1")
        self.streamer.execution("test")
        assert self.streamer.steps[0].runtime_state == "input_received"

    def test_no_duplicate_events(self):
        for _ in range(5):
            self.streamer.planning("dup")
        assert self.streamer.step_count == 5
        types = [s.step_type for s in self.streamer.steps]
        assert types == [StepType.PLANNING] * 5

    def test_step_dict_format(self):
        self.streamer.directive("test")
        d = self.streamer.get_steps_dict()[0]
        assert "event_type" in d
        assert "step_type" in d
        assert "step_id" in d
        assert "timestamp" in d

    def test_stream_lifecycle_sequence(self):
        """完整流式生命周期步骤序列。"""
        steps = [
            (StepType.DIRECTIVE, "Evaluating"),
            (StepType.GOVERNANCE, "Checking"),
            (StepType.PLANNING, "Planning"),
            (StepType.EXECUTION, "Executing"),
            (StepType.MEMORY, "Storing"),
            (StepType.OUTPUT, "Output"),
            (StepType.COMPLETE, "Done"),
        ]
        for st, title in steps:
            self.streamer.emit(st, title)
        assert self.streamer.step_count == 7
        assert self.streamer.steps[-1].step_type == StepType.COMPLETE


class TestStepStreamerWithStateMachine:

    def test_state_transition_consistency(self):
        sm = RuntimeStateMachine()
        streamer = StepStreamer(sm)

        sm.start_turn("t1")
        sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        streamer.directive("Evaluating")
        assert streamer.steps[0].runtime_state == "directive_evaluation"

        sm.transition(RuntimeState.GOVERNANCE_CHECK)
        streamer.governance("Checking")
        assert streamer.steps[1].runtime_state == "governance_check"

        sm.transition(RuntimeState.PLANNING)
        streamer.planning("Planning")
        assert streamer.steps[2].runtime_state == "planning"
