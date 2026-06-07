"""Stock Agent 运行时数据模型

Event = 系统中唯一的事实结构。
RuntimeContext = 轻量上下文。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class StockEventType(enum.Enum):
    DATA_FETCH = "data_fetch"
    ANALYSIS = "analysis"
    LLM_CALL = "llm_call"
    SCREENING = "screening"
    COMPARISON = "comparison"
    USER_ACTION = "user_action"


@dataclass
class StockEvent:
    """选股事件。"""
    event_type: str
    timestamp: str = ""
    stock_code: str | None = None
    strategy: str | None = None
    data: dict = field(default_factory=dict)
    trace_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "stock_code": self.stock_code,
            "strategy": self.strategy,
            "data": self.data,
            "trace_id": self.trace_id,
        }


@dataclass
class RuntimeContext:
    """运行时上下文。"""
    input: str = ""
    events: list = field(default_factory=list)
    trace_id: str = ""
    timestamp: str = ""
    total_latency_s: float = 0.0
    overall_status: str = "pending"

    @property
    def last_event(self):
        return self.events[-1] if self.events else None

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "input": self.input,
            "timestamp": self.timestamp,
            "total_latency_s": self.total_latency_s,
            "overall_status": self.overall_status,
            "event_count": len(self.events),
        }
