"""Event — 统一事件系统

Event = 系统中唯一的持久化结构。
所有 stage 输出、决策、风险、错误均表示为 Event。

EventStore = append-only 事件存储（JSONL 持久化）。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    """统一事件 — 系统中唯一的事实结构。

    Fields:
        trace_id: 执行轨迹 ID
        stage: 阶段名 (load / semantic / validate / schedule / govern / log)
        event_type: 事件类型 (info / decision / risk / error)
        payload: 事件数据
        timestamp:  Unix 时间戳
        metadata:  可选元数据
        runtime_mode:  运行时模式 (chat / task / tool / explore / system)
        directive_profile:  身份 Profile (lightweight / standard / governance / coding)
    """
    trace_id: str
    stage: str
    event_type: str
    payload: dict
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)
    runtime_mode: str = ""
    directive_profile: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class EventStore:
    """Append-only 事件存储 — 唯一事实源。

    所有系统输出必须变成 Event 写入此存储。
    不允许任何模块单独保存状态/报告/日志。
    """

    def __init__(self, base_dir: str = ""):
        self._events: list[Event] = []
        self._base_dir = base_dir or self._default_base_dir()
        self._event_dir = os.path.join(self._base_dir, "runtime", "events")
        os.makedirs(self._event_dir, exist_ok=True)

    # ── Write ──────────────────────────────────────────────────────────────

    def append(self, event: Event) -> None:
        """Append 一个事件（内存 + JSONL 持久化）。"""
        self._events.append(event)
        self._persist_event(event)

    # ── Read ───────────────────────────────────────────────────────────────

    def read_by_trace(self, trace_id: str) -> list[Event]:
        """读取某次执行的全部事件。"""
        events = [e for e in self._events if e.trace_id == trace_id]
        if not events:
            events = self._load_trace(trace_id)
            self._events.extend(events)
        return events

    def read_by_stage(self, trace_id: str, stage: str) -> list[Event]:
        """读取某次执行中特定阶段的事件。"""
        return [e for e in self.read_by_trace(trace_id) if e.stage == stage]

    def list_traces(self) -> list[str]:
        """列出所有 trace_id。"""
        trace_ids = set(e.trace_id for e in self._events)
        if os.path.exists(self._event_dir):
            for fname in os.listdir(self._event_dir):
                if fname.endswith(".jsonl"):
                    trace_ids.add(fname.replace(".jsonl", ""))
        return sorted(trace_ids)

    # ── Projection ─────────────────────────────────────────────────────────

    def project(self, trace_id: str) -> dict[str, Any]:
        """将某次执行的事件流投影为状态摘要。"""
        events = self.read_by_trace(trace_id)
        by_stage: dict[str, list[dict]] = {}
        for e in events:
            by_stage.setdefault(e.stage, []).append({
                "type": e.event_type,
                "payload": e.payload,
                "timestamp": e.timestamp,
            })

        # 从事件中提取计算属性
        risk_scores = []
        final_state = None
        has_error = False
        for e in events:
            if e.event_type == "risk" and "risk_score" in e.payload:
                risk_scores.append(e.payload["risk_score"])
            if e.event_type == "error":
                has_error = True
            if e.event_type == "decision" and e.payload.get("final_state"):
                final_state = e.payload["final_state"]

        return {
            "trace_id": trace_id,
            "stage_count": len(by_stage),
            "stages": list(by_stage.keys()),
            "stage_detail": by_stage,
            "total_events": len(events),
            "risk_score": max(risk_scores) if risk_scores else 0.0,
            "has_error": has_error,
            "final_state": final_state,
        }

    def snapshot(self, label: str = "") -> dict[str, Any]:
        """全量快照 — 所有 trace 的汇总。"""
        all_traces = self.list_traces()
        trace_summaries = []
        for tid in all_traces:
            proj = self.project(tid)
            trace_summaries.append(proj)

        return {
            "snapshot_label": label,
            "snapshot_time": time.time(),
            "total_traces": len(all_traces),
            "traces": trace_summaries,
            "summary": {
                "total": len(all_traces),
                "with_errors": sum(1 for t in trace_summaries if t["has_error"]),
            },
        }

    # ── Persistence ────────────────────────────────────────────────────────

    def _persist_event(self, event: Event) -> None:
        """将事件追加到 trace 的 JSONL 文件。"""
        path = os.path.join(self._event_dir, f"{event.trace_id}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "trace_id": event.trace_id,
                "stage": event.stage,
                "type": event.event_type,
                "payload": event.payload,
                "timestamp": event.timestamp,
                "metadata": event.metadata,
                "runtime_mode": event.runtime_mode,
                "directive_profile": event.directive_profile,
            }, ensure_ascii=False) + "\n")

    def _load_trace(self, trace_id: str) -> list[Event]:
        """从 JSONL 文件加载某次执行的全部事件。"""
        path = os.path.join(self._event_dir, f"{trace_id}.jsonl")
        if not os.path.exists(path):
            return []
        events = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                events.append(Event(
                    trace_id=data["trace_id"],
                    stage=data["stage"],
                    event_type=data["type"],
                    payload=data.get("payload", {}),
                    timestamp=data.get("timestamp", 0.0),
                    metadata=data.get("metadata", {}),
                    runtime_mode=data.get("runtime_mode", ""),
                    directive_profile=data.get("directive_profile", ""),
                ))
        return events

    @staticmethod
    def _default_base_dir() -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
