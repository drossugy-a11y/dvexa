"""Step Events v1 — 流式执行步骤事件模型

每个 RuntimeStep 对应一个可观测的执行步骤。
StepStreamer 按顺序发射，前端实时渲染。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepType(str, Enum):
    DIRECTIVE = "directive"
    GOVERNANCE = "governance"
    PLANNING = "planning"
    EXECUTION = "execution"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    MEMORY = "memory"
    OUTPUT = "output"
    COMPLETE = "complete"
    ERROR = "error"
    BLOCKED = "blocked"
    RECOVERY = "recovery"


@dataclass
class RuntimeStep:
    """单个可观测执行步骤。"""
    step_type: StepType
    title: str = ""
    content: str = ""
    step_id: str = ""
    timestamp: float = 0.0
    runtime_state: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.step_id = self.step_id or f"step-{uuid.uuid4().hex[:8]}"
        self.timestamp = self.timestamp or time.time()

    def to_dict(self) -> dict:
        return {
            "event_type": "runtime_step",
            "step_type": self.step_type.value,
            "step_id": self.step_id,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp,
            "runtime_state": self.runtime_state,
            "metadata": self.metadata,
        }


def make_step(step_type: StepType, title: str = "",
              content: str = "", runtime_state: str = "",
              metadata: dict | None = None) -> RuntimeStep:
    """便捷工厂函数。"""
    return RuntimeStep(
        step_type=step_type,
        title=title,
        content=content,
        runtime_state=runtime_state,
        metadata=metadata or {},
    )
