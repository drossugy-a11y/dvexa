"""DVXReplayEngine v1.91 — 只依赖 EventStore 的重放引擎

所有回放操作 100% 从 EventStore 生成。
不依赖任何 runtime memory。
"""

from __future__ import annotations

from typing import Any

from runtime.event import EventStore


class DVXReplayEngine:
    """执行重放引擎 — 只依赖 EventStore。

    支持：
      - 按 trace_id 完整重放
      - 按阶段局部重放
      - 两次执行之间的差异分析
    """

    def __init__(self, event_store: EventStore):
        self._store = event_store

    # ── 完整重放 ──────────────────────────────────────────────────────────

    def replay(self, trace_id: str) -> dict[str, Any] | None:
        """重放一次完整执行。"""
        events = self._store.read_by_trace(trace_id)
        if not events:
            return None
        return self._reconstruct(trace_id, events)

    def replay_stage(self, trace_id: str, stage: str) -> list[dict] | None:
        """重放特定阶段的执行。"""
        events = self._store.read_by_stage(trace_id, stage)
        if not events:
            return None
        return [
            {
                "trace_id": trace_id,
                "stage": e.stage,
                "type": e.event_type,
                "payload": e.payload,
                "timestamp": e.timestamp,
            }
            for e in events
        ]

    # ── 差异分析 ──────────────────────────────────────────────────────────

    def diff_execution(self, trace_id_1: str, trace_id_2: str) -> dict[str, Any]:
        """对比两次执行的差异（基于 EventStore 投影）。"""
        proj1 = self._store.project(trace_id_1)
        proj2 = self._store.project(trace_id_2)

        if not proj1["stages"] or not proj2["stages"]:
            missing = []
            if not proj1["stages"]:
                missing.append(trace_id_1)
            if not proj2["stages"]:
                missing.append(trace_id_2)
            return {"error": f"Trace(s) not found: {missing}"}

        stages_1 = set(proj1["stages"])
        stages_2 = set(proj2["stages"])
        all_stages = sorted(stages_1 | stages_2)

        stage_diffs: list[dict[str, Any]] = []
        for stage_name in all_stages:
            s1 = proj1["stage_detail"].get(stage_name, [])
            s2 = proj2["stage_detail"].get(stage_name, [])

            # 提取决策/风险事件
            d1 = next((e for e in s1 if e["type"] in ("decision", "risk")), {})
            d2 = next((e for e in s2 if e["type"] in ("decision", "risk")), {})

            p1 = d1.get("payload", {})
            p2 = d2.get("payload", {})

            diff: dict[str, Any] = {
                "stage": stage_name,
                "trace_1": {"status": "present" if s1 else "missing", "risk": p1.get("risk_score")},
                "trace_2": {"status": "present" if s2 else "missing", "risk": p2.get("risk_score")},
            }

            if s1 and s2:
                r1 = p1.get("risk_score", 0)
                r2 = p2.get("risk_score", 0)
                diff["risk_delta"] = round(abs(r1 - r2), 3)
                diff["decision_changed"] = p1.get("summary") != p2.get("summary")
            else:
                diff["risk_delta"] = None
                diff["decision_changed"] = None

            stage_diffs.append(diff)

        overall = {
            "trace_id_1": trace_id_1,
            "trace_id_2": trace_id_2,
            "risk_1": proj1["risk_score"],
            "risk_2": proj2["risk_score"],
            "stage_count_1": proj1["stage_count"],
            "stage_count_2": proj2["stage_count"],
            "final_state_1": proj1["final_state"],
            "final_state_2": proj2["final_state"],
            "divergence": proj1["risk_score"] != proj2["risk_score"],
        }

        return {
            "overall": overall,
            "stage_diffs": stage_diffs,
        }

    def diff_execution_report(self, trace_id_1: str, trace_id_2: str) -> str:
        """生成可读的差异分析报告。"""
        diff = self.diff_execution(trace_id_1, trace_id_2)

        if "error" in diff:
            return f"Error: {diff['error']}"

        lines = [
            "=" * 60,
            "  DVX Execution Diff Report (EventStore)",
            "=" * 60,
            "",
            f"  Trace 1: {trace_id_1}",
            f"  Trace 2: {trace_id_2}",
            "",
            f"  Risk:   {diff['overall']['risk_1']} → {diff['overall']['risk_2']}",
            f"  Divergence: {'YES' if diff['overall']['divergence'] else 'NO'}",
            "",
            "  Stage-by-Stage:",
        ]

        for sd in diff["stage_diffs"]:
            lines.append(
                f"    {sd['stage']}: "
                f"risk {sd['trace_1']['risk']} → {sd['trace_2']['risk']} "
                f"(Δ={sd['risk_delta']})"
            )

        return "\n".join(lines)

    # ── 内部 ──────────────────────────────────────────────────────────────

    def _reconstruct(self, trace_id: str, events: list) -> dict[str, Any]:
        """从事件列表重构执行链视图。"""
        risk_scores = []
        stages = []
        final_state = None

        for e in events:
            stages.append(e.stage)
            if e.event_type == "risk" and "risk_score" in e.payload:
                risk_scores.append(e.payload["risk_score"])
            if e.stage == "schedule" and e.event_type == "decision":
                final_state = e.payload.get("final_state", e.payload.get("state"))

        return {
            "trace_id": trace_id,
            "events": [
                {
                    "stage": e.stage,
                    "type": e.event_type,
                    "payload": e.payload,
                }
                for e in events
            ],
            "stages": stages,
            "final_state": final_state,
            "risk_score": max(risk_scores) if risk_scores else 0.0,
        }
