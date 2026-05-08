"""CapabilityGraph v1.0 — 查询层

纯只读查询，不修改图结构，不产生副作用。
所有输出完全基于已有图结构推导。
"""

from __future__ import annotations

from typing import Any

from runtime.projections.capability_graph.models import (
    CapabilityNode,
    CapabilityEdge,
    CapabilityGraph,
)


def query_capability(graph: CapabilityGraph, node_id: str) -> CapabilityGraph:
    """返回以 node_id 为中心的 1-hop 子图。

    包含：
    - 目标节点自身
    - 所有直接前驱（incoming 1-hop）
    - 所有直接后继（outgoing 1-hop）
    - 连接这些节点的边

    Args:
        graph: 完整图
        node_id: 目标节点 ID

    Returns:
        CapabilityGraph — 局部子图。节点不存在时返回空图。
    """
    target = graph.get_node(node_id)
    if not target:
        return CapabilityGraph(metadata={"error": f"node not found: {node_id}"})

    nodes: dict[str, CapabilityNode] = {node_id: target}
    edges: list[CapabilityEdge] = []

    # 出边
    for edge, neighbor in graph.outgoing(node_id):
        if neighbor.id not in nodes:
            nodes[neighbor.id] = neighbor
        edges.append(edge)

    # 入边
    for edge, neighbor in graph.incoming(node_id):
        if neighbor.id not in nodes:
            nodes[neighbor.id] = neighbor
        edges.append(edge)

    return CapabilityGraph(
        nodes=nodes,
        edges=edges,
        metadata={
            "query": "query_capability",
            "center": node_id,
            "node_type": target.type,
            "hop_count": len(nodes) - 1,
            "edge_count": len(edges),
        },
    )


def find_dependency_chain(graph: CapabilityGraph, node_id: str) -> CapabilityGraph:
    """沿 causal_next 边向上游追溯依赖链。

    从 node_id 出发，沿入边（causal_next）递归追溯到根节点。
    返回完整的依赖链子图。

    Args:
        graph: 完整图
        node_id: 起点节点 ID

    Returns:
        CapabilityGraph — 依赖链子图。节点不存在时返回空图。
    """
    target = graph.get_node(node_id)
    if not target:
        return CapabilityGraph(metadata={"error": f"node not found: {node_id}"})

    nodes: dict[str, CapabilityNode] = {}
    edges: list[CapabilityEdge] = []
    visited: set[str] = set()

    def _traverse_up(current_id: str) -> None:
        if current_id in visited:
            return
        visited.add(current_id)
        node = graph.get_node(current_id)
        if node:
            nodes[current_id] = node

        for edge, neighbor in graph.incoming(current_id):
            if edge.relation_type in ("causal_next",):
                nodes[neighbor.id] = neighbor
                edges.append(edge)
                _traverse_up(neighbor.id)

    _traverse_up(node_id)

    # 按 causal_next 顺序排列
    ordered_ids = _order_chain(nodes, edges, node_id)

    return CapabilityGraph(
        nodes=nodes,
        edges=edges,
        metadata={
            "query": "find_dependency_chain",
            "start": node_id,
            "chain_length": len(nodes),
            "ordered_chain": ordered_ids,
        },
    )


def simulate_impact(graph: CapabilityGraph, node_id: str) -> dict[str, Any]:
    """模拟节点移除的影响。

    计算从该节点出发沿 causal_next 边可达的所有下游节点。
    不修改图，返回影响分析报告。

    Args:
        graph: 完整图
        node_id: 要移除的节点 ID

    Returns:
        dict: 影响分析报告
    """
    if not graph.get_node(node_id):
        return {"error": f"node not found: {node_id}", "affected_count": 0}

    downstream: set[str] = set()
    visited: set[str] = set()

    def _traverse_down(current_id: str) -> None:
        if current_id in visited:
            return
        visited.add(current_id)

        for edge, neighbor in graph.outgoing(current_id):
            if edge.relation_type in ("causal_next", "stage_transition"):
                downstream.add(neighbor.id)
                _traverse_down(neighbor.id)

    _traverse_down(node_id)

    # 分类受影响节点
    affected_nodes = []
    for nid in downstream:
        node = graph.get_node(nid)
        if node:
            affected_nodes.append({
                "id": nid,
                "type": node.type,
                "stage": node.metadata.get("stage", ""),
                "event_type": node.metadata.get("event_type", ""),
            })

    # 按阶段分组
    by_stage: dict[str, list[str]] = {}
    for n in affected_nodes:
        by_stage.setdefault(n["stage"], []).append(n["id"])

    node = graph.get_node(node_id)
    return {
        "query": "simulate_impact",
        "removed_node": {
            "id": node_id,
            "type": node.type if node else "unknown",
            "stage": node.metadata.get("stage", "") if node else "",
        },
        "total_downstream": len(downstream),
        "affected_nodes": affected_nodes,
        "by_stage": {k: {"count": len(v), "nodes": v} for k, v in by_stage.items()},
        "severity": _classify_severity(len(downstream)),
        "has_downstream": len(downstream) > 0,
    }


# ── 辅助工具 ───────────────────────────────────────────────────────


def _order_chain(nodes: dict[str, CapabilityNode],
                 edges: list[CapabilityEdge],
                 end_id: str) -> list[str]:
    """将依赖链按 causal_next 顺序排列（最早 → 最晚）。"""
    # 建立反向映射: target → source
    rev_map: dict[str, str] = {}
    for edge in edges:
        if edge.relation_type == "causal_next":
            rev_map[edge.target_id] = edge.source_id

    ordered = [end_id]
    current = end_id
    while current in rev_map:
        prev = rev_map[current]
        ordered.insert(0, prev)
        current = prev

    return ordered


def _classify_severity(count: int) -> str:
    if count == 0:
        return "none"
    elif count <= 3:
        return "low"
    elif count <= 10:
        return "medium"
    else:
        return "high"
