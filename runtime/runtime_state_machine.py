"""Runtime State Machine v1 — DVexa 统一运行时状态机

ALL runtime behavior MUST flow through this state machine.
No module may independently mutate runtime lifecycle state.

Transition Graph:
  IDLE → INPUT_RECEIVED → DIRECTIVE_EVALUATION → GOVERNANCE_CHECK
    → BLOCKED → IDLE
    → PLANNING → EXECUTING → TOOL_RUNNING → EXECUTING
                            → STREAMING → MEMORY_COMMIT → COMPLETED → IDLE
                            → ERROR → RECOVERY → IDLE
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
# RuntimeState — 12 种运行时状态
# ═══════════════════════════════════════════════════════════════════════


class RuntimeState(str, Enum):
    IDLE = "idle"
    INPUT_RECEIVED = "input_received"
    DIRECTIVE_EVALUATION = "directive_evaluation"
    GOVERNANCE_CHECK = "governance_check"
    PLANNING = "planning"
    EXECUTING = "executing"
    TOOL_RUNNING = "tool_running"
    STREAMING = "streaming"
    MEMORY_COMMIT = "memory_commit"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ERROR = "error"
    RECOVERY = "recovery"


# ═══════════════════════════════════════════════════════════════════════
# 严格转换图 — 只允许定义的边
# ═══════════════════════════════════════════════════════════════════════

_TRANSITIONS: dict[RuntimeState, set[RuntimeState]] = {
    RuntimeState.IDLE: {RuntimeState.INPUT_RECEIVED},
    RuntimeState.INPUT_RECEIVED: {RuntimeState.DIRECTIVE_EVALUATION},
    RuntimeState.DIRECTIVE_EVALUATION: {RuntimeState.GOVERNANCE_CHECK},
    RuntimeState.GOVERNANCE_CHECK: {RuntimeState.BLOCKED, RuntimeState.PLANNING},
    RuntimeState.PLANNING: {RuntimeState.EXECUTING},
    RuntimeState.EXECUTING: {
        RuntimeState.TOOL_RUNNING,
        RuntimeState.STREAMING,
        RuntimeState.MEMORY_COMMIT,
        RuntimeState.ERROR,
    },
    RuntimeState.TOOL_RUNNING: {RuntimeState.EXECUTING, RuntimeState.ERROR},
    RuntimeState.STREAMING: {RuntimeState.MEMORY_COMMIT, RuntimeState.ERROR},
    RuntimeState.MEMORY_COMMIT: {RuntimeState.COMPLETED, RuntimeState.ERROR},
    RuntimeState.COMPLETED: {RuntimeState.IDLE},
    RuntimeState.ERROR: {RuntimeState.RECOVERY, RuntimeState.IDLE},
    RuntimeState.BLOCKED: {RuntimeState.IDLE},
    RuntimeState.RECOVERY: {RuntimeState.IDLE, RuntimeState.ERROR},
}


# ═══════════════════════════════════════════════════════════════════════
# StateTransitionEvent
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class StateTransitionEvent:
    from_state: RuntimeState
    to_state: RuntimeState
    timestamp: float
    metadata: dict = field(default_factory=dict)
    turn_id: str = ""

    def to_dict(self) -> dict:
        return {
            "from": self.from_state.value,
            "to": self.to_state.value,
            "timestamp": self.timestamp,
            "turn_id": self.turn_id,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════════════
# RuntimeStateMachine
# ═══════════════════════════════════════════════════════════════════════


class RuntimeStateMachine:
    """统一运行时状态机 — 所有运行时行为的单一事实来源。

    线程安全。所有转换经过严格验证。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._state = RuntimeState.IDLE
        self._history: list[StateTransitionEvent] = []
        self._start_time = time.time()
        self._turn_id = ""
        self._observers: list[callable] = []

    # ── 核心 API ──────────────────────────────────────────────────────

    def get_state(self) -> RuntimeState:
        return self._state

    def can_transition(self, next_state: RuntimeState) -> bool:
        """检查转换是否合法（不修改状态）。"""
        allowed = _TRANSITIONS.get(self._state, set())
        return next_state in allowed

    def transition(self, next_state: RuntimeState,
                   metadata: dict | None = None) -> StateTransitionEvent:
        """执行状态转换。失败时抛出 RuntimeError。"""
        with self._lock:
            allowed = _TRANSITIONS.get(self._state, set())
            if next_state not in allowed:
                raise RuntimeError(
                    f"INVALID STATE TRANSITION: {self._state.value} → {next_state.value}. "
                    f"Allowed: {[s.value for s in allowed]}"
                )

            from_state = self._state
            self._state = next_state

            event = StateTransitionEvent(
                from_state=from_state,
                to_state=next_state,
                timestamp=time.time(),
                metadata=metadata or {},
                turn_id=self._turn_id,
            )
            self._history.append(event)

        # Notify observers outside lock
        for obs in self._observers:
            try:
                obs(event)
            except Exception:
                pass

        return event

    def rollback(self) -> StateTransitionEvent | None:
        """回滚到上一个有效状态。"""
        with self._lock:
            if len(self._history) < 2:
                raise RuntimeError(
                    f"CANNOT ROLLBACK: history too short ({len(self._history)})"
                )
            # Find the state before current (skip transitions from the same from_state)
            current = self._state
            for i in range(len(self._history) - 2, -1, -1):
                candidate = self._history[i].to_state
                if candidate != current:
                    # Check if the rollback target allows transition TO current
                    allowed_from_candidate = _TRANSITIONS.get(candidate, set())
                    if current in allowed_from_candidate or candidate == RuntimeState.IDLE:
                        previous = candidate
                        break
            else:
                previous = RuntimeState.IDLE

            from_state = self._state
            self._state = previous

            event = StateTransitionEvent(
                from_state=from_state,
                to_state=previous,
                timestamp=time.time(),
                metadata={"rollback": True, "from": from_state.value},
                turn_id=self._turn_id,
            )
            self._history.append(event)

        for obs in self._observers:
            try:
                obs(event)
            except Exception:
                pass

        return event

    # ── 便捷方法 ──────────────────────────────────────────────────────

    def start_turn(self, turn_id: str = "") -> StateTransitionEvent:
        """INPUT_RECEIVED → 开始一轮新执行。"""
        self._turn_id = turn_id
        return self.transition(RuntimeState.INPUT_RECEIVED, {"turn_id": turn_id})

    def complete_turn(self) -> StateTransitionEvent:
        """COMPLETED → IDLE。"""
        return self.transition(RuntimeState.IDLE, {"turn_complete": True})

    def mark_blocked(self, reason: str = "") -> StateTransitionEvent:
        return self.transition(RuntimeState.BLOCKED, {"reason": reason})

    def mark_error(self, reason: str = "") -> StateTransitionEvent:
        return self.transition(RuntimeState.ERROR, {"reason": reason})

    def mark_recovery(self) -> StateTransitionEvent:
        return self.transition(RuntimeState.RECOVERY)

    # ── 观察者 ─────────────────────────────────────────────────────────

    def subscribe(self, callback: callable) -> None:
        """订阅状态转换事件。"""
        self._observers.append(callback)

    def unsubscribe(self, callback: callable) -> None:
        if callback in self._observers:
            self._observers.remove(callback)

    # ── 查询 ───────────────────────────────────────────────────────────

    @property
    def history(self) -> list[StateTransitionEvent]:
        return list(self._history)

    @property
    def turn_id(self) -> str:
        return self._turn_id

    @property
    def uptime(self) -> float:
        return round(time.time() - self._start_time, 3)

    @property
    def is_idle(self) -> bool:
        return self._state == RuntimeState.IDLE

    @property
    def is_running(self) -> bool:
        return self._state not in (
            RuntimeState.IDLE, RuntimeState.COMPLETED,
            RuntimeState.ERROR, RuntimeState.BLOCKED,
        )

    def to_dict(self) -> dict:
        return {
            "current_state": self._state.value,
            "turn_id": self._turn_id,
            "uptime": self.uptime,
            "is_idle": self.is_idle,
            "is_running": self.is_running,
            "transition_count": len(self._history),
            "last_transition": self._history[-1].to_dict() if self._history else None,
            "history": [e.to_dict() for e in self._history[-20:]],
        }
