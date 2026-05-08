"""CapabilityGraph v1.0 — 图构建器

纯 EventStore 投影。不依赖运行时状态，不产生副作用。
"""

from __future__ import annotations

from typing import Any

from runtime.event import EventStore, Event
from runtime.projections.capability_graph.models import (
    CapabilityNode,
    CapabilityEdge,
    CapabilityGraph,
)


class CapabilityGraphBuilder:
    """CapabilityGraph 构建器。

    仅从 EventStore 投影，无外部系统依赖。
    SchemaRegistry/governance 仅作为可选元数据补充（非事实源）。
    """

    def __init__(
        self,
        event_store: EventStore,
        skill_registry: Any | None = None,
        governor: Any | None = None,
    ):
        self._store = event_store
        self._registry = skill_registry
        self._governor = governor

    # ── 主入口 ──────────────────────────────────────────────────────────

    def build_graph(self, trace_id: str | None = None) -> CapabilityGraph:
        """构建图。

        Args:
            trace_id: 指定 trace 则构建单次执行子图；None 则构建全量图。

        Returns:
            CapabilityGraph — 纯 EventStore 投影。
        """
        if trace_id:
            events = self._store.read_by_trace(trace_id)
        else:
            events = self._load_all_events()

        if not events:
            return CapabilityGraph(metadata={"empty": True, "reason": "no events"})

        sorted_events = sorted(events, key=lambda e: (e.timestamp or 0.0, id(e)))
        by_trace: dict[str, list[Event]] = {}
        for e in sorted_events:
            by_trace.setdefault(e.trace_id, []).append(e)

        nodes: dict[str, CapabilityNode] = {}
        edges: list[CapabilityEdge] = {}

        for tid, trace_events in by_trace.items():
            self._build_trace_subgraph(tid, trace_events, nodes, edges)

        self._enrich_from_registry(nodes)

        metadata = {
            "trace_count": len(by_trace),
            "total_events": len(sorted_events),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "built_from": "EventStore",
        }

        return CapabilityGraph(nodes=nodes, edges=list(edges.values()), metadata=metadata)

    def build_execution_graph(self, trace_id: str) -> CapabilityGraph:
        """便捷方法：构建单次执行的子图。"""
        return self.build_graph(trace_id=trace_id)

    # ── 内部构建 ────────────────────────────────────────────────────────

    def _build_trace_subgraph(
        self,
        trace_id: str,
        events: list[Event],
        nodes: dict[str, CapabilityNode],
        edges: dict[str, CapabilityEdge],
    ) -> None:
        """为单个 trace 构建子图：节点 + 边。"""
        if not events:
            return

        # trace 根节点
        root_id = f"trace:{trace_id}"
        if root_id not in nodes:
            nodes[root_id] = CapabilityNode(
                id=root_id,
                type="trace",
                ref_event_id=trace_id,
                metadata={
                    "event_count": len(events),
                    "stages": list({e.stage for e in events}),
                },
            )

        stage_first_idx: dict[str, int] = {}

        for i, evt in enumerate(events):
            node_id = f"{trace_id}:evt:{i}"
            payload_snapshot = self._snapshot_payload(evt.payload)

            nodes[node_id] = CapabilityNode(
                id=node_id,
                type=evt.stage,
                ref_event_id=trace_id,
                metadata={
                    "event_type": evt.event_type,
                    "payload": payload_snapshot,
                    "timestamp": evt.timestamp,
                    "index": i,
                    "stage": evt.stage,
                },
            )

            # same_trace: 每个事件连接到 trace 根节点
            ekey = f"same_trace:{root_id}->{node_id}"
            if ekey not in edges:
                edges[ekey] = CapabilityEdge(
                    source_id=root_id,
                    target_id=node_id,
                    relation_type="same_trace",
                    metadata={"trace_id": trace_id, "event_index": i},
                )

            # causal_next: 连续事件连接
            if i > 0:
                prev_id = f"{trace_id}:evt:{i - 1}"
                ckey = f"causal_next:{prev_id}->{node_id}"
                if ckey not in edges:
                    edges[ckey] = CapabilityEdge(
                        source_id=prev_id,
                        target_id=node_id,
                        relation_type="causal_next",
                        metadata={"trace_id": trace_id, "from_index": i - 1, "to_index": i},
                    )

            # stage_transition: 第一个出现该 stage 的事件连接到前一个 stage 的首次出现
            if evt.stage not in stage_first_idx:
                stage_first_idx[evt.stage] = i
                if len(stage_first_idx) > 1:
                    prev_stage = [s for s in stage_first_idx if s != evt.stage][-1]
                    prev_i = stage_first_idx[prev_stage]
                    prev_id = f"{trace_id}:evt:{prev_i}"
                    skey = f"stage_transition:{prev_id}->{node_id}"
                    if skey not in edges:
                        edges[skey] = CapabilityEdge(
                            source_id=prev_id,
                            target_id=node_id,
                            relation_type="stage_transition",
                            metadata={
                                "trace_id": trace_id,
                                "from_stage": prev_stage,
                                "to_stage": evt.stage,
                            },
                        )

        # governance 相关事件的额外连接
        self._link_governance_events(events, nodes, edges, trace_id)

    def _link_governance_events(
        self,
        events: list[Event],
        nodes: dict[str, CapabilityNode],
        edges: dict[str, CapabilityEdge],
        trace_id: str,
    ) -> None:
        """连接治理事件到对应 payload 中引用的节点。"""
        for i, evt in enumerate(events):
            node_id = f"{trace_id}:evt:{i}"

            # 从 payload 中提取引用的事件/节点
            refs = self._extract_references(evt.payload)
            for j, ref in enumerate(refs):
                ekey = f"governance_ref:{node_id}->ref:{j}"
                if ekey not in edges:
                    edges[ekey] = CapabilityEdge(
                        source_id=node_id,
                        target_id=ref,
                        relation_type="causal_next",
                        metadata={"reference": True, "trace_id": trace_id},
                    )

    # ── 工具 ────────────────────────────────────────────────────────────

    @staticmethod
    def _snapshot_payload(payload: dict, max_depth: int = 3) -> dict:
        """截断 payload 防止过大。"""
        if max_depth <= 0:
            return {"_truncated": True}
        result = {}
        for k, v in payload.items():
            if isinstance(v, dict):
                result[k] = CapabilityGraphBuilder._snapshot_payload(v, max_depth - 1)
            elif isinstance(v, (list, tuple)) and len(v) > 10:
                result[k] = list(v[:10]) + ["..."]
            elif isinstance(v, str) and len(v) > 500:
                result[k] = v[:500] + "..."
            else:
                result[k] = v
        return result

    @staticmethod
    def _extract_references(payload: dict) -> list[str]:
        """从 payload 中提取 trace 引用。"""
        refs = []
        if isinstance(payload, dict):
            for k, v in payload.items():
                if k in ("trace_id", "ref_trace") and isinstance(v, str):
                    refs.append(f"trace:{v}")
                if k == "decision_ref" and isinstance(v, str):
                    refs.append(f"trace:{v}")
        return refs

    def _load_all_events(self) -> list[Event]:
        """加载 EventStore 中所有事件。"""
        traces = self._store.list_traces()
        events = []
        for tid in traces:
            events.extend(self._store.read_by_trace(tid))
        return events

    def _enrich_from_registry(self, nodes: dict[str, CapabilityNode]) -> None:
        """可选：用 SkillRegistry 元数据补充节点。"""
        if not self._registry:
            return
        registry_skills = getattr(self._registry, "all_skills", None)
        if not registry_skills:
            return
        skills = registry_skills()
        for node in nodes.values():
            for skill_name, skill_def in skills.items():
                if skill_name in str(node.metadata.get("payload", {})):
                    node.metadata.setdefault("_enriched", []).append({
                        "source": "SkillRegistry",
                        "skill_name": skill_name,
                        "description": getattr(skill_def, "description", ""),
                    })

    @staticmethod
    def reconstruct_from_events(events: list[Event]) -> CapabilityGraph:
        """从事件列表重建图。

        纯函数 — 用于 EventStore 回放重建。
        """
        n_events = len(events)
        by_trace: dict[str, list[Event]] = {}
        for e in events:
            by_trace.setdefault(e.trace_id, []).append(e)

        nodes: dict[str, CapabilityNode] = {}
        edges: dict[str, CapabilityEdge] = {}

        for tid, trace_events in by_trace.items():
            builder = CapabilityGraphBuilder.__new__(CapabilityGraphBuilder)
            builder._registry = None
            builder._governor = None
            builder._store = None  # type: ignore
            builder._build_trace_subgraph(tid, trace_events, nodes, edges)

        return CapabilityGraph(
            nodes=nodes,
            edges=list(edges.values()),
            metadata={
                "reconstructed": True,
                "total_events": n_events,
                "trace_count": len(by_trace),
            },
        )
