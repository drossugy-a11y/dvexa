"""Turn Lock v1 — 轮次锁定系统

防止一次用户输入触发多次 assistant 生成。

状态机:
  IDLE → ACTIVE → STREAMING → COMPLETED → IDLE

规则:
  - 每次只有一轮 ACTIVE
  - ACTIVE 期间忽略新 LLM 触发
  - COMPLETED → 仅在最终 output commit 后 reset
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from threading import Lock


class TurnState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    STREAMING = "streaming"
    COMPLETED = "completed"


@dataclass
class TurnRecord:
    turn_id: str
    state: TurnState
    started_at: float
    completed_at: float = 0.0
    user_input: str = ""
    assistant_output: str = ""

    def duration(self) -> float:
        end = self.completed_at or time.time()
        return round(end - self.started_at, 3)


class TurnLock:
    """轮次锁 — 保证单轮单输出。

    线程安全 (Lock)。
    """

    def __init__(self):
        self._lock = Lock()
        self._state = TurnState.IDLE
        self._current_turn: TurnRecord | None = None
        self._history: list[TurnRecord] = []

    # ── Public API ────────────────────────────────────────────────────

    def can_start_turn(self) -> bool:
        """检查是否可以开始新轮次。"""
        return self._state == TurnState.IDLE

    def start_turn(self, user_input: str = "") -> TurnRecord:
        """开始新轮次。"""
        with self._lock:
            if self._state != TurnState.IDLE:
                raise RuntimeError(
                    f"TURN_LOCK: cannot start turn in state {self._state.value}"
                )
            self._state = TurnState.ACTIVE
            self._current_turn = TurnRecord(
                turn_id=f"turn-{uuid.uuid4().hex[:12]}",
                state=TurnState.ACTIVE,
                started_at=time.time(),
                user_input=user_input,
            )
            return self._current_turn

    def mark_streaming(self) -> None:
        """标记为流式输出中。"""
        with self._lock:
            if self._state != TurnState.ACTIVE:
                raise RuntimeError(
                    f"TURN_LOCK: cannot mark streaming from {self._state.value}"
                )
            self._state = TurnState.STREAMING
            if self._current_turn:
                self._current_turn.state = TurnState.STREAMING

    def complete_turn(self, output: str = "") -> TurnRecord:
        """完成当前轮次。"""
        with self._lock:
            if self._state not in (TurnState.ACTIVE, TurnState.STREAMING):
                raise RuntimeError(
                    f"TURN_LOCK: cannot complete turn in state {self._state.value}"
                )
            old_state = self._state
            self._state = TurnState.COMPLETED
            if self._current_turn:
                self._current_turn.state = TurnState.COMPLETED
                self._current_turn.completed_at = time.time()
                self._current_turn.assistant_output = output
                self._history.append(self._current_turn)
            record = self._current_turn
            self._current_turn = None
            self._state = TurnState.IDLE  # auto-reset
            return record

    def is_locked(self) -> bool:
        """是否锁定（不允许新 LLM 调用）。"""
        return self._state in (TurnState.ACTIVE, TurnState.STREAMING)

    @property
    def state(self) -> TurnState:
        return self._state

    @property
    def current_turn(self) -> TurnRecord | None:
        return self._current_turn

    @property
    def turn_count(self) -> int:
        return len(self._history)

    def get_history(self, limit: int = 10) -> list[dict]:
        return [
            {
                "turn_id": t.turn_id,
                "state": t.state.value,
                "duration": t.duration(),
                "user_input": t.user_input[:100],
                "has_output": bool(t.assistant_output),
            }
            for t in self._history[-limit:]
        ]

    def reset(self) -> None:
        """强制重置（用于异常恢复）。"""
        with self._lock:
            self._state = TurnState.IDLE
            self._current_turn = None
