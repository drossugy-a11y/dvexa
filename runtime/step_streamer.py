"""StepStreamer v1 — 流式步骤发射引擎"""

from __future__ import annotations

import logging
from typing import Any, Callable

from runtime.step_events import StepType, RuntimeStep
from runtime.runtime_state_machine import RuntimeStateMachine

logger = logging.getLogger("dvexa.streamer")

StepCallback = Callable[[RuntimeStep], None]


class StepStreamer:
    """流式步骤发射器。"""

    def __init__(self, state_machine: RuntimeStateMachine | None = None,
                 ws_push: Callable[[dict], None] | None = None):
        self._sm = state_machine
        self._ws = ws_push
        self._steps: list[RuntimeStep] = []
        self._observers: list[StepCallback] = []

    def set_ws_push(self, callback: Callable[[dict], None]) -> None:
        """设置 WebSocket 推送回调。"""
        self._ws = callback

    def emit(self, step_type: StepType, title: str = "",
             content: str = "", metadata: dict | None = None) -> RuntimeStep:
        state = self._sm.get_state().value if self._sm else ""
        step = RuntimeStep(
            step_type=step_type, title=title, content=content,
            runtime_state=state, metadata=metadata or {},
        )
        self._steps.append(step)
        payload = step.to_dict()

        if self._ws:
            try:
                self._ws(payload)
            except Exception as e:
                logger.warning("WS push failed for step %s: %s", step_type.value, e)

        for obs in self._observers:
            try:
                obs(step)
            except Exception as e:
                logger.warning("Observer failed for step %s: %s", step_type.value, e)

        return step

    def directive(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.DIRECTIVE, title, content, metadata)

    def governance(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.GOVERNANCE, title, content, metadata)

    def planning(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.PLANNING, title, content, metadata)

    def execution(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.EXECUTION, title, content, metadata)

    def tool_call(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.TOOL_CALL, title, content, metadata)

    def tool_result(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.TOOL_RESULT, title, content, metadata)

    def thinking(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.THINKING, title, content, metadata)

    def memory(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.MEMORY, title, content, metadata)

    def output(self, title="", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.OUTPUT, title, content, metadata)

    def complete(self, title="Completed", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.COMPLETE, title, content, metadata)

    def error(self, title="Error", content="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.ERROR, title, content, metadata)

    def blocked(self, reason="", metadata=None) -> RuntimeStep:
        return self.emit(StepType.BLOCKED, "Execution Blocked", reason, metadata)

    def subscribe(self, callback: StepCallback) -> None:
        self._observers.append(callback)

    def unsubscribe(self, callback: StepCallback) -> None:
        if callback in self._observers:
            self._observers.remove(callback)

    @property
    def steps(self) -> list[RuntimeStep]:
        return list(self._steps)

    def get_steps_dict(self) -> list[dict]:
        return [s.to_dict() for s in self._steps]

    @property
    def step_count(self) -> int:
        return len(self._steps)

    def clear(self) -> None:
        self._steps.clear()
