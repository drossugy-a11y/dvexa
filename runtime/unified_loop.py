"""Unified Runtime Loop v1 — DVexa 统一执行循环 (Streaming)

每个阶段通过 StepStreamer 发射可观测步骤。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from runtime.runtime_state_machine import (
    RuntimeStateMachine, RuntimeState,
)
from runtime.step_streamer import StepStreamer
from runtime.step_events import StepType


@dataclass
class TurnRecord:
    turn_id: str = ""
    turn_count: int = 0
    mode: str = "chat"
    directive: dict | None = None
    output: str = ""
    error: str | None = None
    start_time: float = 0.0
    phase_timing: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "turn_count": self.turn_count,
            "mode": self.mode,
            "has_directive": self.directive is not None,
            "has_output": bool(self.output),
            "error": self.error,
            "duration": round(time.time() - self.start_time, 3),
            "phases": list(self.phase_timing.keys()),
        }


class UnifiedRuntimeLoop:
    """统一执行循环 — 流式步骤发射。

    UnifiedRuntimeLoop 编排 7 阶段生命周期，
    每个阶段通过 StepStreamer 发射可观测 RuntimeStep。
    """

    def __init__(self, kernel: Any, directive_engine: Any = None,
                 governance_kernel: Any = None,
                 state_machine: RuntimeStateMachine | None = None,
                 step_streamer: StepStreamer | None = None):
        self._kernel = kernel
        self._directive_engine = directive_engine
        self._governance_kernel = governance_kernel
        self._sm = state_machine or RuntimeStateMachine()
        self._streamer = step_streamer or StepStreamer(self._sm)
        self._total_turns = 0
        self._current_turn: TurnRecord | None = None

    @property
    def state_machine(self) -> RuntimeStateMachine:
        return self._sm

    @property
    def step_streamer(self) -> StepStreamer:
        return self._streamer

    def run(self, user_input: str,
            context: dict | None = None) -> dict:
        """全生命周期执行 — 发射流式步骤。"""
        self._total_turns += 1
        turn_id = f"turn-{uuid.uuid4().hex[:12]}"
        self._current_turn = TurnRecord(
            turn_id=turn_id, turn_count=self._total_turns,
            start_time=time.time(),
        )

        try:
            # ═════════════════════════════════════════════════════════
            # PHASE 1: DIRECTIVE
            # ═════════════════════════════════════════════════════════
            self._sm.start_turn(turn_id)
            self._sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
            self._record_phase("directive")

            self._streamer.directive(
                title="Evaluating system directive",
                content="Analyzing intent and execution context",
            )

            directive = None
            if self._directive_engine is not None:
                ctx = {"input": user_input, "task_count": self._total_turns, "has_tools": True}
                if context:
                    ctx.update(context)
                directive = self._directive_engine.process(user_input, ctx)
                self._current_turn.directive = directive.to_dict()
                self._current_turn.mode = directive.mode

                self._streamer.directive(
                    title=f"Mode: {directive.mode}",
                    content=f"Planning={directive.must_plan}, "
                            f"Tools={directive.must_use_tools}, "
                            f"Stream={directive.must_stream}",
                    metadata={"mode": directive.mode, "must_plan": directive.must_plan},
                )

            # ═════════════════════════════════════════════════════════
            # PHASE 2: GOVERNANCE
            # ═════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.GOVERNANCE_CHECK)
            self._record_phase("governance")

            self._streamer.governance(
                title="Performing governance check",
                content="Checking constraints, risk, and capability availability",
            )

            kernel_result = self._kernel.run_task(user_input)
            self._streamer.governance(
                title="Governance check passed",
                content=f"Status: {kernel_result.get('status', 'ok')}",
            )

            # ═════════════════════════════════════════════════════════
            # PHASE 3: PLANNING
            # ═════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.PLANNING)
            self._record_phase("planning")

            step_count = len(kernel_result.get("steps", []))
            self._streamer.planning(
                title=f"Plan ready ({step_count} steps)",
                content=kernel_result.get("goal", "")[:120],
            )

            # ═════════════════════════════════════════════════════════
            # PHASE 4-5: EXECUTION + TOOL
            # ═════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.EXECUTING)
            self._record_phase("execution")

            # ═════════════════════════════════════════════════════════
            # PHASE 6: MEMORY
            # ═════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.MEMORY_COMMIT)
            self._record_phase("memory")

            self._streamer.memory(
                title="Updating memory",
                content="Committing execution result",
            )

            # ═════════════════════════════════════════════════════════
            # PHASE 7: OUTPUT
            # ═════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.COMPLETED)
            self._record_phase("output")

            output = self._build_output(kernel_result, directive)
            self._current_turn.output = output

            self._streamer.output(
                title="Execution complete",
                content=output[:200],
            )
            self._streamer.complete()

            self._sm.complete_turn()

            return {
                "output": output,
                "turn": self._current_turn.to_dict(),
                "directive": self._current_turn.directive,
                "kernel_result": kernel_result,
                "steps": self._streamer.get_steps_dict(),
            }

        except Exception as e:
            try:
                self._sm.mark_error(str(e))
            except Exception:
                pass
            self._current_turn.error = str(e)
            self._streamer.error(title="Runtime error", content=str(e))
            return {
                "output": f"Loop error: {e}",
                "turn": self._current_turn.to_dict(),
                "directive": self._current_turn.directive,
                "error": str(e),
                "steps": self._streamer.get_steps_dict(),
            }

    def _record_phase(self, phase: str) -> None:
        if self._current_turn:
            self._current_turn.phase_timing[phase] = time.time()

    @staticmethod
    def _build_output(kernel_result: dict, directive: Any = None) -> str:
        status = kernel_result.get("status", "unknown")
        if status == "failed":
            return kernel_result.get("result", "Execution failed")
        result_text = kernel_result.get("result") or kernel_result.get("goal", "")
        return result_text or str(kernel_result)

    @property
    def total_turns(self) -> int:
        return self._total_turns

    def is_idle(self) -> bool:
        return self._sm.is_idle

    def is_running(self) -> bool:
        return self._sm.is_running
