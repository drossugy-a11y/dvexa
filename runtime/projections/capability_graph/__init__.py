"""CapabilityGraph v1.0 — EventStore 投影层

纯只读投影：EventStore → Graph
不引入新语义，不修改任何系统模块，不持久化独立状态。
"""

from runtime.projections.capability_graph.models import (
    CapabilityNode,
    CapabilityEdge,
    CapabilityGraph,
)
from runtime.projections.capability_graph.builder import CapabilityGraphBuilder
from runtime.projections.capability_graph.queries import (
    query_capability,
    find_dependency_chain,
    simulate_impact,
)
from runtime.projections.capability_graph.exporter import export_graph

__all__ = [
    "CapabilityNode",
    "CapabilityEdge",
    "CapabilityGraph",
    "CapabilityGraphBuilder",
    "query_capability",
    "find_dependency_chain",
    "simulate_impact",
    "export_graph",
]
