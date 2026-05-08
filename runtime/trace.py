"""ExecutionTrace v1.91 — Event 执行轨迹工具集

对 RuntimeContext.events (list[Event]) 的查询和分析层。
"""

from __future__ import annotations

import json
from typing import Any

from runtime.models import ExecutionStage, RuntimeContext


class ExecutionTrace:
    """执行轨迹工具 — 对 RuntimeContext.events 的查询和分析。

    所有操作基于 EventStore 事件，不依赖历史数据。
    """

    def __init__(self, ctx: RuntimeContext):
        self._ctx = ctx
        self._events = list(getattr(ctx, "events", []))

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get(self, stage: ExecutionStage) -> Any | None:
        """按阶段查询事件（返回最后一个匹配的事件）。"""
        sv = stage.value if isinstance(stage, ExecutionStage) else stage
        for e in reversed(self._events):
            if e.stage == sv:
                return e
        return None

    def get_events_by_type(self, stage: str, event_type: str) -> list:
        """按阶段+类型查询事件列表。"""
        return [e for e in self._events if e.stage == stage and e.event_type == event_type]

    def all(self) -> list:
        """返回全部事件。"""
        return list(self._events)

    def stages(self) -> list[str]:
        """返回所有已执行阶段的名称列表。"""
        seen: list[str] = []
        for e in self._events:
            if e.stage not in seen:
                seen.append(e.stage)
        return seen

    def errors(self) -> list:
        """返回所有 error 类型事件。"""
        return [e for e in self._events if e.event_type == "error"]

    def has_errors(self) -> bool:
        """是否有任何 error 事件。"""
        return any(e.event_type == "error" for e in self._events)

    # ── 分析 ──────────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """执行轨迹摘要（从事件派生）。"""
        return {
            "trace_id": self._ctx.trace_id,
            "total_stages": len(self.stages()),
            "completed_stages": self.stages(),
            "errors": [{"stage": e.stage, "detail": str(e.payload)} for e in self.errors()],
            "total_events": len(self._events),
            "total_latency_s": round(self._ctx.total_latency_s, 5),
            "risk_progression": [{"stage": e.stage, "risk": e.payload.get("risk_score", 0)} for e in self._events if e.event_type in ("decision", "risk")],
            "passed": self._ctx.passed,
        }

    def decision_chain(self) -> list[dict[str, Any]]:
        """提取决策链 — 所有 decision 类型事件。"""
        return [
            {
                "stage": e.stage,
                "decision": e.payload.get("reason", e.payload.get("summary", "")),
                "risk_score": e.payload.get("risk_score", 0),
                "event_type": e.event_type,
            }
            for e in self._events
            if e.event_type == "decision"
        ]

    def to_json(self, indent: int = 2) -> str:
        """序列化为可读 JSON。"""
        return json.dumps({
            "trace_id": self._ctx.trace_id,
            "input": self._ctx.input[:100],
            "total_latency_s": self._ctx.total_latency_s,
            "overall_status": self._ctx.overall_status,
            "passed": self._ctx.passed,
            "risk_score": self._ctx.risk_score,
            "events": [
                {
                    "stage": e.stage,
                    "type": e.event_type,
                    "payload": _summary(e.payload),
                    "timestamp": e.timestamp,
                }
                for e in self._events
            ],
        }, indent=indent, ensure_ascii=False)

    def to_text(self) -> str:
        """格式化为可读文本。"""
        lines = [
            f"Execution Trace: {self._ctx.trace_id}",
            f"Input: {self._ctx.input[:100]}",
            f"Status: {self._ctx.overall_status}",
            f"Passed: {self._ctx.passed}",
            f"Risk Score: {self._ctx.risk_score}",
            f"Total Events: {len(self._events)}",
            "",
        ]

        for event in self._events:
            icon = {
                "info": "ℹ",
                "decision": "◆",
                "risk": "⚠",
                "error": "✗",
            }.get(event.event_type, "•")
            lines.append(f"  [{icon}] {event.stage} ({event.event_type})")
            risk = event.payload.get("risk_score", "")
            lines.append(f"        risk={risk}" if risk else "")

        return "\n".join(lines)


def _summary(obj: Any) -> Any:
    """截断大 payload。"""
    if isinstance(obj, dict):
        return {k: _summary(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_summary(v) for v in obj[:20]]
    s = str(obj)
    if len(s) > 200:
        return s[:200] + "..."
    return obj
