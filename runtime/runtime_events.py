"""Runtime Events v1 — 运行时事件类型

由 RuntimeStateMachine 在每次转换时发射。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeEvent:
    """运行时事件 — 状态机转换的外部表示。"""
    event_type: str  # "state_transition" | "error" | "recovery" | "blocked"
    from_state: str
    to_state: str
    timestamp: float
    metadata: dict = field(default_factory=dict)
    turn_id: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.event_type,
            "from": self.from_state,
            "to": self.to_state,
            "timestamp": self.timestamp,
            "turn_id": self.turn_id,
            "metadata": self.metadata,
        }


def state_transition_to_event(
    from_state: str, to_state: str,
    turn_id: str = "", metadata: dict | None = None,
) -> RuntimeEvent:
    """从状态转换创建事件。"""
    event_type = "state_transition"
    if to_state == "error":
        event_type = "error"
    elif to_state == "recovery":
        event_type = "recovery"
    elif to_state == "blocked":
        event_type = "blocked"
    elif to_state == "completed":
        event_type = "completed"

    return RuntimeEvent(
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        timestamp=time.time(),
        metadata=metadata or {},
        turn_id=turn_id,
    )
