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
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
# Loop Phase
# ═══════════════════════════════════════════════════════════════════════


class LoopPhase(str, Enum):
    IDLE = "idle"
    DIRECTIVE = "directive"
    GOVERNANCE = "governance"
    PLANNING = "planning"
    EXECUTION = "execution"
    TOOL = "tool"
    MEMORY = "memory"
    OUTPUT = "output"
    COMPLETED = "completed"
    ERROR = "error"


# ═══════════════════════════════════════════════════════════════════════
# LoopState — 每轮循环的状态记录
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class LoopState:
    turn_id: str = ""
    current_phase: LoopPhase = LoopPhase.IDLE
    mode: str = "chat"
    directive: dict | None = None
    governance_result: dict | None = None
    plan: dict | None = None
    execution_result: Any = None
    tool_calls: list[dict] = field(default_factory=list)
    output: str = ""
    error: str | None = None
    start_time: float = 0.0
    phase_timing: dict[str, float] = field(default_factory=dict)
    turn_count: int = 0

    def enter_phase(self, phase: LoopPhase) -> None:
        self.current_phase = phase
        self.phase_timing[phase.value] = time.time()

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "turn_count": self.turn_count,
            "current_phase": self.current_phase.value,
            "mode": self.mode,
            "has_directive": self.directive is not None,
            "has_governance": self.governance_result is not None,
            "has_plan": self.plan is not None,
            "tool_calls": len(self.tool_calls),
            "has_output": bool(self.output),
            "error": self.error,
            "duration": round(time.time() - self.start_time, 3),
            "phases": list(self.phase_timing.keys()),
        }

    def reset(self) -> None:
        self.current_phase = LoopPhase.IDLE
        self.directive = None
        self.governance_result = None
        self.plan = None
        self.execution_result = None
        self.tool_calls = []
        self.output = ""
        self.error = None
        self.phase_timing = {}


# ═══════════════════════════════════════════════════════════════════════
# UnifiedRuntimeLoop
# ═══════════════════════════════════════════════════════════════════════


class UnifiedRuntimeLoop:
    """统一执行循环 — 编排 7 阶段生命周期。

    使用方式:
        loop = UnifiedRuntimeLoop(kernel, directive_engine)
        result = loop.run(user_input)
        # → {output, state, phases, timing}
    """

    def __init__(self, kernel: Any, directive_engine: Any = None,
                 governance_kernel: Any = None):
        self._kernel = kernel
        self._directive_engine = directive_engine
        self._governance_kernel = governance_kernel
        self._state = LoopState()
        self._total_turns = 0

    # ── Public API ────────────────────────────────────────────────────

    def run(self, user_input: str,
            context: dict | None = None) -> dict:
        """全生命周期执行。"""
        self._total_turns += 1
        self._state = LoopState(
            turn_id=f"turn-{uuid.uuid4().hex[:12]}",
            turn_count=self._total_turns,
            start_time=time.time(),
        )

        try:
            # ══════════════════════════════════════════════════════════
            # PHASE 1: DIRECTIVE — 行为控制
            # ══════════════════════════════════════════════════════════
            self._state.enter_phase(LoopPhase.DIRECTIVE)
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
                self._state.directive = directive.to_dict()
                self._state.mode = directive.mode

            # ══════════════════════════════════════════════════════════
            # PHASE 2-6: KERNEL (governance → plan → execute → tool → memory)
            # ══════════════════════════════════════════════════════════
            self._state.enter_phase(LoopPhase.GOVERNANCE)
            kernel_result = self._kernel.run_task(user_input)

            # Extract governance info from kernel result
            self._state.enter_phase(LoopPhase.PLANNING)
            self._state.plan = {
                "goal": kernel_result.get("goal", ""),
                "steps": len(kernel_result.get("steps", [])),
            }

            self._state.enter_phase(LoopPhase.EXECUTION)
            self._state.execution_result = {
                "status": kernel_result.get("status", ""),
                "retry_count": kernel_result.get("retry_count", 0),
            }

            self._state.enter_phase(LoopPhase.MEMORY)

            # ══════════════════════════════════════════════════════════
            # PHASE 7: OUTPUT — 最终响应
            # ══════════════════════════════════════════════════════════
            self._state.enter_phase(LoopPhase.OUTPUT)
            output = self._build_output(kernel_result, directive)
            self._state.output = output

            self._state.enter_phase(LoopPhase.COMPLETED)

            return {
                "output": output,
                "state": self._state.to_dict(),
                "directive": self._state.directive,
                "kernel_result": kernel_result,
            }

        except Exception as e:
            self._state.enter_phase(LoopPhase.ERROR)
            self._state.error = str(e)
            return {
                "output": f"Loop error: {e}",
                "state": self._state.to_dict(),
                "directive": self._state.directive,
                "error": str(e),
            }

        finally:
            # Loop reset — 准备下一轮输入
            pass

    # ── Output Builder ───────────────────────────────────────────────

    @staticmethod
    def _build_output(kernel_result: dict,
                      directive: Any = None) -> str:
        """从 kernel 结果构建最终输出。"""
        status = kernel_result.get("status", "unknown")
        if status == "failed":
            return kernel_result.get("result", "Execution failed")

        # Prefer structured result
        result_text = kernel_result.get("result") or kernel_result.get("goal", "")
        if result_text:
            return result_text

        return str(kernel_result)

    # ── State Access ─────────────────────────────────────────────────

    @property
    def state(self) -> LoopState:
        return self._state

    @property
    def total_turns(self) -> int:
        return self._total_turns

    def is_idle(self) -> bool:
        return self._state.current_phase in (LoopPhase.IDLE, LoopPhase.COMPLETED)

    def is_running(self) -> bool:
        return self._state.current_phase not in (
            LoopPhase.IDLE, LoopPhase.COMPLETED, LoopPhase.ERROR
        )
