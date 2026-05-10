"""StepStreamer v1 — 流式步骤发射引擎

将同步执行转换为按序可观测的 RuntimeStep 流。
每个步骤立即推送到 WebSocket + 写入事件日志。
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from runtime.step_events import StepType, RuntimeStep, make_step
from runtime.runtime_state_machine import RuntimeStateMachine, RuntimeState


StepCallback = Callable[[RuntimeStep], None]


class StepStreamer:
    """流式步骤发射器。

    用法:
        streamer = StepStreamer(state_machine, emitter)
        streamer.emit(StepType.PLANNING, "Generating plan", "Decomposing task")
    """

    def __init__(self, state_machine: RuntimeStateMachine | None = None,
                 ws_push: Callable[[dict], None] | None = None):
        self._sm = state_machine
        self._ws = ws_push
        self._steps: list[RuntimeStep] = []
        self._observers: list[StepCallback] = []

    # ── 核心发射 ──────────────────────────────────────────────────────

    def emit(self, step_type: StepType, title: str = "",
             content: str = "", metadata: dict | None = None) -> RuntimeStep:
        """发射一个执行步骤。"""
        state = self._sm.get_state().value if self._sm else ""
        step = RuntimeStep(
            step_type=step_type,
            title=title,
            content=content,
            runtime_state=state,
            metadata=metadata or {},
        )
        self._steps.append(step)
        payload = step.to_dict()

        # WebSocket push
        if self._ws:
            try:
                self._ws(payload)
            except Exception:
                pass

        # Observer notification
        for obs in self._observers:
            try:
                obs(step)
            except Exception:
                pass

        return step

    # ── 便捷方法 ──────────────────────────────────────────────────────

    def directive(self, title: str = "", content: str = "",
                  metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.DIRECTIVE, title, content, metadata)

    def governance(self, title: str = "", content: str = "",
                   metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.GOVERNANCE, title, content, metadata)

    def planning(self, title: str = "", content: str = "",
                 metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.PLANNING, title, content, metadata)

    def execution(self, title: str = "", content: str = "",
                  metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.EXECUTION, title, content, metadata)

    def tool_call(self, title: str = "", content: str = "",
                  metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.TOOL_CALL, title, content, metadata)

    def tool_result(self, title: str = "", content: str = "",
                    metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.TOOL_RESULT, title, content, metadata)

    def thinking(self, title: str = "", content: str = "",
                 metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.THINKING, title, content, metadata)

    def memory(self, title: str = "", content: str = "",
               metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.MEMORY, title, content, metadata)

    def output(self, title: str = "", content: str = "",
               metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.OUTPUT, title, content, metadata)

    def complete(self, title: str = "Completed", content: str = "",
                 metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.COMPLETE, title, content, metadata)

    def error(self, title: str = "Error", content: str = "",
              metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.ERROR, title, content, metadata)

    def blocked(self, reason: str = "",
                metadata: dict | None = None) -> RuntimeStep:
        return self.emit(StepType.BLOCKED, "Execution Blocked", reason, metadata)

    # ── 观察者 ────────────────────────────────────────────────────────

    def subscribe(self, callback: StepCallback) -> None:
        self._observers.append(callback)

    def unsubscribe(self, callback: StepCallback) -> None:
        if callback in self._observers:
            self._observers.remove(callback)

    # ── 查询 ──────────────────────────────────────────────────────────

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
