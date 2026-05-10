"""Unified Runtime Loop v1 — DVexa 统一执行循环

All behavior MUST go through a single unified loop:

INPUT → DIRECTIVE → GOVERNANCE → PLAN → EXECUTE → TOOL → MEMORY → OUTPUT → LOOP

红线:
  - 不 bypass 现有 kernel/executor/governance
  - 只编排，不重新实现
  - 完全确定性
  - 每轮输出后重置状态
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from runtime.runtime_state_machine import (
    RuntimeStateMachine, RuntimeState,
)


# ═══════════════════════════════════════════════════════════════════════
# TurnRecord — 每轮循环的记录
# ═══════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════
# UnifiedRuntimeLoop
# ═══════════════════════════════════════════════════════════════════════


class UnifiedRuntimeLoop:
    """统一执行循环 — 编排 7 阶段生命周期。

    使用 RuntimeStateMachine 作为单一状态源。

    使用方式:
        loop = UnifiedRuntimeLoop(kernel, directive_engine, state_machine)
        result = loop.run(user_input)
    """

    def __init__(self, kernel: Any, directive_engine: Any = None,
                 governance_kernel: Any = None,
                 state_machine: RuntimeStateMachine | None = None):
        self._kernel = kernel
        self._directive_engine = directive_engine
        self._governance_kernel = governance_kernel
        self._sm = state_machine or RuntimeStateMachine()
        self._total_turns = 0
        self._current_turn: TurnRecord | None = None

    # ── Public API ────────────────────────────────────────────────────

    @property
    def state_machine(self) -> RuntimeStateMachine:
        return self._sm

    def run(self, user_input: str,
            context: dict | None = None) -> dict:
        """全生命周期执行。"""
        self._total_turns += 1
        turn_id = f"turn-{uuid.uuid4().hex[:12]}"
        self._current_turn = TurnRecord(
            turn_id=turn_id,
            turn_count=self._total_turns,
            start_time=time.time(),
        )

        try:
            # ══════════════════════════════════════════════════════════
            # PHASE 1: DIRECTIVE
            # ══════════════════════════════════════════════════════════
            self._sm.start_turn(turn_id)
            self._sm.transition(RuntimeState.DIRECTIVE_EVALUATION,
                                {"phase": "directive"})
            self._record_phase("directive")

            directive = None
            if self._directive_engine is not None:
                ctx = {
                    "input": user_input,
                    "task_count": self._total_turns,
                    "has_tools": True,
                }
                if context:
                    ctx.update(context)
                directive = self._directive_engine.process(user_input, ctx)
                self._current_turn.directive = directive.to_dict()
                self._current_turn.mode = directive.mode

            # ══════════════════════════════════════════════════════════
            # PHASE 2: GOVERNANCE
            # ══════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.GOVERNANCE_CHECK,
                                {"phase": "governance"})
            self._record_phase("governance")
            kernel_result = self._kernel.run_task(user_input)

            # ══════════════════════════════════════════════════════════
            # PHASE 3: PLANNING
            # ══════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.PLANNING,
                                {"phase": "planning"})
            self._record_phase("planning")

            # ══════════════════════════════════════════════════════════
            # PHASE 4-5: EXECUTION + TOOL
            # ══════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.EXECUTING,
                                {"phase": "execution"})
            self._record_phase("execution")

            # ══════════════════════════════════════════════════════════
            # PHASE 6: MEMORY
            # ══════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.MEMORY_COMMIT,
                                {"phase": "memory"})
            self._record_phase("memory")

            # ══════════════════════════════════════════════════════════
            # PHASE 7: OUTPUT
            # ══════════════════════════════════════════════════════════
            self._sm.transition(RuntimeState.COMPLETED,
                                {"phase": "output"})
            self._record_phase("output")

            output = self._build_output(kernel_result, directive)
            self._current_turn.output = output

            # Reset to IDLE
            self._sm.complete_turn()

            return {
                "output": output,
                "turn": self._current_turn.to_dict(),
                "directive": self._current_turn.directive,
                "kernel_result": kernel_result,
            }

        except Exception as e:
            try:
                self._sm.mark_error(str(e))
            except Exception:
                pass
            self._current_turn.error = str(e)
            return {
                "output": f"Loop error: {e}",
                "turn": self._current_turn.to_dict(),
                "directive": self._current_turn.directive,
                "error": str(e),
            }

    # ── Internal ──────────────────────────────────────────────────────

    def _record_phase(self, phase: str) -> None:
        if self._current_turn:
            self._current_turn.phase_timing[phase] = time.time()

    @staticmethod
    def _build_output(kernel_result: dict,
                      directive: Any = None) -> str:
        status = kernel_result.get("status", "unknown")
        if status == "failed":
            return kernel_result.get("result", "Execution failed")
        result_text = kernel_result.get("result") or kernel_result.get("goal", "")
        if result_text:
            return result_text
        return str(kernel_result)

    # ── State Access ──────────────────────────────────────────────────

    @property
    def total_turns(self) -> int:
        return self._total_turns

    def is_idle(self) -> bool:
        return self._sm.is_idle

    def is_running(self) -> bool:
        return self._sm.is_running
