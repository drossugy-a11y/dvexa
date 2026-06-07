"""Event Store — 选股事件存储（append-only JSONL）

事件类型：
  - data_fetch: 数据获取
  - analysis: 分析过程
  - llm_call: LLM 调用
  - screening: 筛选
  - comparison: 对比
  - user_action: 用户操作
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any


EVENT_TYPES = {
    "data_fetch": "数据获取",
    "analysis": "分析过程",
    "llm_call": "LLM调用",
    "screening": "筛选",
    "comparison": "对比",
    "user_action": "用户操作",
}


class StockEvent:
    __slots__ = ("event_type", "timestamp", "stock_code", "strategy",
                 "data", "trace_id")

    def __init__(self, event_type: str, data: dict,
                 stock_code: str = None, strategy: str = None,
                 trace_id: str = None):
        self.event_type = event_type
        self.timestamp = datetime.now().isoformat()
        self.stock_code = stock_code
        self.strategy = strategy
        self.data = data
        self.trace_id = trace_id or f"trc-{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "stock_code": self.stock_code,
            "strategy": self.strategy,
            "data": self.data,
            "trace_id": self.trace_id,
        }


class StockEventStore:
    """Append-only JSONL 事件存储。"""

    def __init__(self, filepath: str = "data/events.jsonl"):
        self._filepath = filepath
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        self._events: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self._filepath):
            with open(self._filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

    def append(self, event) -> None:
        if isinstance(event, dict):
            event.setdefault("timestamp", datetime.now().isoformat())
            event.setdefault("trace_id", f"trc-{uuid.uuid4().hex[:12]}")
            d = event
        elif isinstance(event, StockEvent):
            d = event.to_dict()
        else:
            d = {"event_type": "unknown", "data": str(event),
                 "timestamp": datetime.now().isoformat()}
        self._events.append(d)
        with open(self._filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    def query(self, trace_id: str) -> list[dict]:
        return [e for e in self._events if e.get("trace_id") == trace_id]

    def query_by_stock(self, stock_code: str) -> list[dict]:
        return [e for e in self._events if e.get("stock_code") == stock_code]

    def query_by_type(self, event_type: str) -> list[dict]:
        return [e for e in self._events if e.get("event_type") == event_type]

    def get_recent(self, n: int = 50) -> list[dict]:
        return self._events[-n:]

    @property
    def count(self) -> int:
        return len(self._events)
