"""Evolution Tracker v1.0 — 能力演化追踪器

追踪所有能力的演化历史。Append-only 记录到 DvexaZSK/evolution/。

设计红线:
  - append-only: 永不修改已写入记录
  - deterministic: 纯计算输出
  - 不触发能力变更: 只记录不干预
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EvolutionTracker:
    """能力演化追踪器 — 记录能力生命周期的所有变更。

    持久化到 DvexaZSK/evolution/capability_evolution.json (JSONL)。
    """

    def __init__(self, output_dir: str | None = None):
        self._events: list[dict[str, Any]] = []
        self._output_dir = Path(output_dir) if output_dir else \
            Path(__file__).parent.parent / "DvexaZSK" / "evolution"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ── 记录 ──────────────────────────────────────────────────────────────

    def _record(self, event_type: str, capability_id: str,
                data: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "event_type": event_type,
            "capability_id": capability_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        self._events.append(event)
        self._persist_event(event)
        return event

    def record_capability_change(self, capability_id: str, *,
                                 field: str,
                                 old_value: Any,
                                 new_value: Any) -> dict[str, Any]:
        return self._record("capability_change", capability_id, {
            "field": field,
            "old_value": str(old_value),
            "new_value": str(new_value),
        })

    def record_adoption(self, capability_id: str, *,
                        source: str = "",
                        source_type: str = "") -> dict[str, Any]:
        return self._record("adoption", capability_id, {
            "source": source,
            "source_type": source_type,
        })

    def record_failure(self, capability_id: str, *,
                       error: str = "",
                       context: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._record("failure", capability_id, {
            "error": error,
            "context": context or {},
        })

    def record_stabilization(self, capability_id: str, *,
                             previous_maturity: str = "",
                             new_maturity: str = "",
                             metrics: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._record("stabilization", capability_id, {
            "previous_maturity": previous_maturity,
            "new_maturity": new_maturity,
            "metrics": metrics or {},
        })

    def record_governance_decision(self, capability_id: str, *,
                                   decision: str,
                                   reason: str = "") -> dict[str, Any]:
        return self._record("governance_decision", capability_id, {
            "decision": decision,
            "reason": reason,
        })

    def record_assimilation(self, capability_id: str, *,
                            source_repo: str = "",
                            pattern_name: str = "",
                            review_result: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._record("assimilation", capability_id, {
            "source_repo": source_repo,
            "pattern_name": pattern_name,
            "review_result": review_result or {},
        })

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get_events(self, capability_id: str) -> list[dict[str, Any]]:
        return [e for e in self._events if e["capability_id"] == capability_id]

    def get_all_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def get_event_count(self, capability_id: str | None = None) -> int:
        if capability_id:
            return len(self.get_events(capability_id))
        return len(self._events)

    def get_adoption_count(self) -> int:
        return sum(1 for e in self._events if e["event_type"] == "adoption")

    def get_failure_count(self, capability_id: str | None = None) -> int:
        events = self.get_events(capability_id) if capability_id else self._events
        return sum(1 for e in events if e["event_type"] == "failure")

    def get_stabilization_count(self) -> int:
        return sum(1 for e in self._events if e["event_type"] == "stabilization")

    # ── 报告 ──────────────────────────────────────────────────────────────

    def generate_evolution_report(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        by_capability: dict[str, int] = {}
        adoptions: list[str] = []
        failures: list[str] = []

        for e in self._events:
            etype = e["event_type"]
            cid = e["capability_id"]
            by_type[etype] = by_type.get(etype, 0) + 1
            by_capability[cid] = by_capability.get(cid, 0) + 1

            if etype == "adoption":
                adoptions.append(cid)
            elif etype == "failure":
                failures.append(cid)

        most_active = sorted(by_capability.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_events": len(self._events),
            "by_event_type": by_type,
            "adoption_count": len(adoptions),
            "failure_count": len(failures),
            "adopted_capabilities": sorted(set(adoptions)),
            "failed_capabilities": sorted(set(failures)),
            "most_active_capabilities": most_active[:10],
            "event_capability_count": len(by_capability),
        }

    def save_report(self, filepath: str | None = None) -> str:
        report = self.generate_evolution_report()
        path = Path(filepath) if filepath else \
            self._output_dir / "capability_evolution.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return str(path)

    # ── 持久化 ────────────────────────────────────────────────────────────

    def _persist_event(self, event: dict[str, Any]) -> None:
        path = self._output_dir / "capability_evolution.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def load_from_disk(self) -> int:
        """从磁盘加载历史事件（用于恢复）。返回加载事件数。"""
        path = self._output_dir / "capability_evolution.jsonl"
        if not path.exists():
            return 0
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        event = json.loads(line)
                        self._events.append(event)
                        count += 1
                    except json.JSONDecodeError:
                        pass
        return count
