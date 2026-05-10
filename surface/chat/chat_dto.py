"""Chat Runtime DTO — 消息/响应/时间线事件"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
from enum import Enum


class EventType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    PLANNING_STARTED = "planning_started"
    GOVERNANCE_DECISION = "governance_decision"
    TOOL_EXECUTION = "tool_execution"
    MEMORY_HIT = "memory_hit"
    EXECUTION_COMPLETE = "execution_complete"
    ERROR = "error"
    # Streaming protocol events
    STREAM_STARTED = "stream_started"
    MESSAGE_CHUNK = "message_chunk"
    STREAM_COMPLETED = "stream_completed"
    STREAM_ERROR = "stream_error"


@dataclass
class ChatMessageDTO:
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: str = ""
    task_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TimelineEventDTO:
    event_type: str
    task_id: str
    step_id: str = ""
    tool: str = ""
    status: str = "running"
    strategy: str = ""
    decision: str = ""
    reason: str = ""
    content: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class ChatResponseDTO:
    task_id: str
    status: str  # "accepted" | "running" | "completed" | "error"
    role: str = "assistant"
    content: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
