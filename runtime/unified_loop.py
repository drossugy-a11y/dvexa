"""Unified Runtime Loop v1 — DVexa 统一执行循环 (Streaming)

每个阶段通过 StepStreamer 发射可观测步骤。
使用 TurnLock 防止 re-entry。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from runtime.runtime_state_machine import (
    RuntimeStateMachine, RuntimeState,
)
from runtime.step_streamer import StepStreamer
from runtime.turn_lock import TurnLock, TurnState


logger = logging.getLogger(__name__)


class UnifiedRuntimeLoop:
    """统一执行循环 — 流式步骤发射。

    编排 7 阶段生命周期 (DIRECTIVE → GOVERNANCE → PLAN → EXECUTE → MEMORY → OUTPUT)，
    每个阶段通过 StepStreamer 发射可观测 RuntimeStep，
    使用 TurnLock 保证单轮单输出。
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
        self._turn_lock = TurnLock()
        self._total_turns = 0
        self._kernel_result: dict = {}
        self._last_input: str = ""

    @property
    def state_machine(self) -> RuntimeStateMachine:
        return self._sm

    @property
    def step_streamer(self) -> StepStreamer:
        return self._streamer

    @property
    def turn_lock(self) -> TurnLock:
        return self._turn_lock

    def run(self, user_input: str,
            context: dict | None = None) -> dict:
        """全生命周期执行 — 发射流式步骤。"""
        try:
            turn = self._turn_lock.start_turn(user_input, self._total_turns + 1)
            self._last_input = user_input
        except RuntimeError:
            return {
                "output": "System busy: another turn is in progress",
                "error": "TURN_LOCKED",
                "steps": self._streamer.get_steps_dict(),
            }

        self._total_turns += 1

        try:
            self._phase_directive(user_input, context, turn)
            self._phase_governance(user_input)
            self._phase_planning()
            self._phase_execute()
            self._turn_lock.mark_streaming()
            self._sm.transition(RuntimeState.STREAMING)
            self._phase_memory()
            output = self._phase_output(turn)

            self._turn_lock.complete_turn(output)
            self._sm.complete_turn()

            return {
                "output": output,
                "turn": turn.to_dict(),
                "directive": turn.directive,
                "kernel_result": self._kernel_result,
                "steps": self._streamer.get_steps_dict(),
            }

        except Exception as e:
            return self._handle_error(e, turn)

    # ── Phase methods ──────────────────────────────────────────────────

    def _phase_directive(self, user_input: str, context: dict | None,
                         turn: Any) -> None:
        """PHASE 1: DIRECTIVE — 意图分析与执行模式选择。"""
        self._sm.start_turn(turn.turn_id)
        self._sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self._record_phase("directive")

        self._streamer.directive(
            title="Evaluating system directive",
            content="Analyzing intent and execution context",
        )

        if self._directive_engine is None:
            return

        ctx = {"input": user_input, "task_count": self._total_turns, "has_tools": True}
        if context:
            ctx.update(context)
        directive = self._directive_engine.process(user_input, ctx)
        turn.directive = directive.to_dict()
        turn.mode = directive.mode

        self._streamer.directive(
            title=f"Mode: {directive.mode}",
            content=f"Planning={directive.must_plan}, "
                    f"Tools={directive.must_use_tools}, "
                    f"Stream={directive.must_stream}",
            metadata={"mode": directive.mode, "must_plan": directive.must_plan},
        )

    def _phase_governance(self, user_input: str) -> None:
        """PHASE 2: GOVERNANCE — 约束检查与风险评分。"""
        self._sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self._record_phase("governance")

        self._streamer.governance(
            title="Performing governance check",
            content="Checking constraints, risk, and capability availability",
        )

    def _phase_planning(self) -> None:
        """PHASE 3: PLANNING — 任务计划生成。"""
        self._sm.transition(RuntimeState.PLANNING)
        self._record_phase("planning")

        step_count = len(self._kernel_result.get("steps", []))
        self._streamer.planning(
            title=f"Plan ready ({step_count} steps)",
            content=self._kernel_result.get("goal", "")[:120],
        )

    def _phase_execute(self) -> None:
        """PHASE 4-5: EXECUTION + TOOL — 执行步骤。"""
        self._sm.transition(RuntimeState.EXECUTING)
        self._kernel_result = self._kernel.run_task(self._last_input)

    def _phase_memory(self) -> None:
        """PHASE 6: MEMORY — 记忆提交。"""
        self._sm.transition(RuntimeState.MEMORY_COMMIT)
        self._record_phase("memory")

        self._streamer.memory(
            title="Updating memory",
            content="Committing execution result",
        )

    def _phase_output(self, turn: Any) -> str:
        """PHASE 7: OUTPUT — 构建输出并发射完成事件。"""
        self._sm.transition(RuntimeState.COMPLETED)

        status = self._kernel_result.get("status", "unknown")
        if status == "failed":
            output = self._kernel_result.get("result", "Execution failed")
        else:
            output = (self._kernel_result.get("result")
                      or self._kernel_result.get("goal", "")
                      or str(self._kernel_result))

        turn.output = output

        self._streamer.output(
            title="Execution complete",
            content=output[:200],
        )
        self._streamer.complete()

        return output

    def _handle_error(self, e: Exception, turn: Any) -> dict:
        """异常处理 — 状态修复 + 错误发射。"""
        try:
            self._sm.mark_error(str(e))
        except Exception as sm_err:
            logger.warning("State machine error during error handling: %s", sm_err)
        turn.error = str(e)
        self._streamer.error(title="Runtime error", content=str(e))
        self._turn_lock.reset()
        return {
            "output": f"Loop error: {e}",
            "turn": turn.to_dict(),
            "directive": turn.directive,
            "error": str(e),
            "steps": self._streamer.get_steps_dict(),
        }

    def _record_phase(self, phase: str) -> None:
        """记录阶段执行时间到当前 turn。"""
        turn = self._turn_lock.current_turn
        if turn:
            turn.phase_timing[phase] = time.time()

    # ── Convenience properties ─────────────────────────────────────────

    @property
    def total_turns(self) -> int:
        return self._total_turns

    def is_idle(self) -> bool:
        return self._sm.is_idle

    def is_running(self) -> bool:
        return self._sm.is_running

    def can_start_turn(self) -> bool:
        return self._turn_lock.can_start_turn()
