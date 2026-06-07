"""Stock Agent Runtime Engine — 选股运行时调度器

简化为：接收查询 → 调度分析 → 记录事件 → 返回结果。
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from storage.event_store import StockEventStore


class StockRuntimeEngine:
    """选股运行时引擎。"""

    def __init__(self, executor, governance=None, event_store=None):
        self._executor = executor
        self._governance = governance
        self._event_store = event_store or StockEventStore()

    def run_screening(self, conditions: dict) -> dict:
        trace_id = f"trc-{uuid.uuid4().hex[:12]}"
        start = time.perf_counter()

        self._event_store.append({
            "event_type": "screening",
            "trace_id": trace_id,
            "data": {"conditions": conditions},
        })

        result = self._executor.execute_screening(conditions)

        self._event_store.append({
            "event_type": "screening",
            "trace_id": trace_id,
            "data": {"result_count": result.get("total", 0)},
        })

        result["trace_id"] = trace_id
        result["latency_s"] = round(time.perf_counter() - start, 3)
        return result

    def run_analysis(self, stock_code: str) -> dict:
        trace_id = f"trc-{uuid.uuid4().hex[:12]}"
        start = time.perf_counter()

        self._event_store.append({
            "event_type": "analysis",
            "trace_id": trace_id,
            "stock_code": stock_code,
            "data": {"action": "deep_analysis"},
        })

        result = self._executor.execute_deep_analysis(stock_code)

        self._event_store.append({
            "event_type": "analysis",
            "trace_id": trace_id,
            "stock_code": stock_code,
            "data": {"score": result.get("score", 0)},
        })

        result["trace_id"] = trace_id
        result["latency_s"] = round(time.perf_counter() - start, 3)
        return result

    def run_comparison(self, stock_codes: list) -> dict:
        trace_id = f"trc-{uuid.uuid4().hex[:12]}"
        start = time.perf_counter()

        self._event_store.append({
            "event_type": "comparison",
            "trace_id": trace_id,
            "data": {"codes": stock_codes},
        })

        result = self._executor.execute_comparison(stock_codes)

        self._event_store.append({
            "event_type": "comparison",
            "trace_id": trace_id,
            "data": {"codes": stock_codes},
        })

        result["trace_id"] = trace_id
        result["latency_s"] = round(time.perf_counter() - start, 3)
        return result

    @property
    def event_store(self) -> StockEventStore:
        return self._event_store
