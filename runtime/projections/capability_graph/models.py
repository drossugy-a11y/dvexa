"""CapabilityGraph v1.0 — 数据模型

EventStore 派生图的不可变数据模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityNode:
    """图节点 — 派生自 Event。

    所有节点均由 EventStore 中的事件派生。
    不引入独立语义分类。
    """
    id: str
    type: str
    ref_event_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    is_derived: bool = True


@dataclass(frozen=True)
class CapabilityEdge:
    """图边 — 仅从事件排序/因果派生。"""
    source_id: str
    target_id: str
    relation_type: str  # causal_next | same_trace | stage_transition
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityGraph:
    """CapabilityGraph — 只读投影容器。"""
    nodes: dict[str, CapabilityNode] = field(default_factory=dict)
    edges: list[CapabilityEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self._adjacency: dict[str, list[tuple[str, str, int]]] = {}
        self._reverse_adjacency: dict[str, list[tuple[str, str, int]]] = {}
        for i, edge in enumerate(self.edges):
            self._adjacency.setdefault(edge.source_id, []).append(
                (edge.relation_type, edge.target_id, i)
            )
            self._reverse_adjacency.setdefault(edge.target_id, []).append(
                (edge.relation_type, edge.source_id, i)
            )

    def get_node(self, node_id: str) -> CapabilityNode | None:
        return self.nodes.get(node_id)

    def get_edge(self, index: int) -> CapabilityEdge | None:
        if 0 <= index < len(self.edges):
            return self.edges[index]
        return None

    def outgoing(self, node_id: str,
                 relation_type: str | None = None) -> list[tuple[CapabilityEdge, CapabilityNode]]:
        """返回从 node_id 出发的边和目标节点。"""
        result = []
        for rel, target_id, idx in self._adjacency.get(node_id, []):
            if relation_type and rel != relation_type:
                continue
            target = self.nodes.get(target_id)
            if target:
                result.append((self.edges[idx], target))
        return result

    def incoming(self, node_id: str,
                 relation_type: str | None = None) -> list[tuple[CapabilityEdge, CapabilityNode]]:
        """返回指向 node_id 的边和源节点。"""
        result = []
        for rel, source_id, idx in self._reverse_adjacency.get(node_id, []):
            if relation_type and rel != relation_type:
                continue
            source = self.nodes.get(source_id)
            if source:
                result.append((self.edges[idx], source))
        return result

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def node_ids_by_type(self, node_type: str) -> list[str]:
        return [nid for nid, n in self.nodes.items() if n.type == node_type]
