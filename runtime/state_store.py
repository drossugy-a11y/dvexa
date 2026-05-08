"""RuntimeStateStore v1.91 — EventStore 投影层

不再作为独立状态存储。
所有数据通过 EventStore 读写。
提供向下兼容接口和 DevLog 投影。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from runtime.event import EventStore


class RuntimeStateStore:
    """运行时状态存储 — EventStore 投影层。

    所有写操作委托给 EventStore.append()。
    read_state / list_traces / query_state 从 EventStore.project() 派生。

    DevLog 写入保留为 EventStore 的可选投影。
    """

    def __init__(self, base_dir: str = "", event_store: EventStore | None = None):
        self._event_store = event_store or EventStore(base_dir)
        self._base_dir = base_dir or self._default_base_dir()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def event_store(self) -> EventStore:
        return self._event_store

    # ── Write (委托给 EventStore) ─────────────────────────────────────────

    def write_state(self, ctx: Any) -> str:
        """写入状态（将 ctx.events 全部写入 EventStore）。

        Returns:
            伪路径（兼容旧接口）。
        """
        for event in getattr(ctx, "events", []):
            self._event_store.append(event)

        trace_id = getattr(ctx, "trace_id", "unknown")
        trace_dir = os.path.join(self._base_dir, "runtime", "traces")
        os.makedirs(trace_dir, exist_ok=True)
        file_path = os.path.join(trace_dir, f"{trace_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(ctx.to_dict() if hasattr(ctx, "to_dict") else {}, f, indent=2, ensure_ascii=False)
        return file_path

    # ── DevLog 投影 ───────────────────────────────────────────────────────

    def append_to_devlog(self, ctx: Any) -> str | None:
        """将执行摘要追加到 DevLog（EventStore 的 markdown 投影）。"""
        today = datetime.now().strftime("%Y-%m-%d")
        devlog_dir = os.path.join(self._base_dir, "DvexaZSK", "devlog")
        os.makedirs(devlog_dir, exist_ok=True)

        log_file = os.path.join(devlog_dir, f"{today}_runtime_engine.md")
        trace_id = getattr(ctx, "trace_id", "unknown")
        passed = ctx.passed if hasattr(ctx, "passed") else False
        risk_score = ctx.risk_score if hasattr(ctx, "risk_score") else 0.0
        total_latency_s = getattr(ctx, "total_latency_s", 0.0)
        stage_count = len(getattr(ctx, "events", []))
        status_icon = "✅" if passed else "❌"

        entry = (
            f"\n## Runtime Run: {trace_id} {status_icon}\n"
            f"- **Timestamp**: {getattr(ctx, 'timestamp', '')}\n"
            f"- **Input**: `{getattr(ctx, 'input', '')[:200]}`\n"
            f"- **Passed**: {passed}\n"
            f"- **Risk Score**: {risk_score}\n"
            f"- **Latency**: {total_latency_s:.5f}s\n"
            f"- **Stages**: {stage_count} events\n"
            f"- **(EventStore)** 事件已持久化到 runtime/events/{trace_id}.jsonl\n"
        )

        if not os.path.exists(log_file):
            header = (
                f"# Runtime Engine Log — {today}\n"
                f"\n"
                f"EventStore 投影 — 完整事件见 runtime/events/{{trace_id}}.jsonl\n"
            )
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(header)

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)

        return log_file

    # ── Read (从 EventStore 派生) ─────────────────────────────────────────

    def read_state(self, trace_id: str) -> Any | None:
        """按 trace_id 读取（返回 EventStore 投影的 dict）。"""
        events = self._event_store.read_by_trace(trace_id)
        if not events:
            return None
        return self._event_store.project(trace_id)

    def list_traces(self) -> list[dict[str, Any]]:
        """列出所有 trace 摘要（从 EventStore 派生）。"""
        trace_ids = self._event_store.list_traces()
        summaries = []
        for tid in trace_ids:
            proj = self._event_store.project(tid)
            summaries.append({
                "trace_id": tid,
                "risk_score": proj["risk_score"],
                "stage_count": proj["stage_count"],
                "total_events": proj["total_events"],
                "has_error": proj["has_error"],
            })
        return summaries

    def query_state(self, **filters: Any) -> list[dict]:
        """按条件查询（从 EventStore 投影过滤）。"""
        all_projs = [self._event_store.project(tid) for tid in self._event_store.list_traces()]
        results = []
        for proj in all_projs:
            match = True
            if "risk_gt" in filters and proj["risk_score"] <= filters["risk_gt"]:
                match = False
            if "risk_lt" in filters and proj["risk_score"] >= filters["risk_lt"]:
                match = False
            if "has_error" in filters and proj["has_error"] != filters["has_error"]:
                match = False
            if match:
                results.append(proj)
        return results

    def snapshot_state(self, label: str = "") -> str:
        """生成快照（EventStore.snapshot() 的 JSON 投影）。"""
        snapshot_dir = os.path.join(self._base_dir, "runtime", "snapshots")
        os.makedirs(snapshot_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = f"_{label}" if label else ""
        file_path = os.path.join(snapshot_dir, f"snapshot_{timestamp}{safe_label}.json")

        snapshot = self._event_store.snapshot(label)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

        return file_path

    @staticmethod
    def _default_base_dir() -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
