"""Tests for CapabilityEvolutionGraph.

Verifies node/edge operations, JSON export, registry import, and timeline queries.
"""

from __future__ import annotations

import pytest

from capabilities.evolution_graph import CapabilityEvolutionGraph


class TestCapabilityEvolutionGraph:
    """CapabilityEvolutionGraph 单元测试。"""

    # ── Node Tests ──────────────────────────────────────────────────────

    def test_add_node(self):
        """add_node 在内部 _nodes 字典中创建条目。"""
        graph = CapabilityEvolutionGraph()
        graph.add_node("skill:test", "Test Skill")
        assert "skill:test" in graph._nodes
        assert graph._nodes["skill:test"]["name"] == "Test Skill"
        assert graph._nodes["skill:test"]["lifecycle"] == "active"

    def test_add_node_with_dependencies(self):
        """add_node 支持依赖列表参数。"""
        graph = CapabilityEvolutionGraph()
        graph.add_node(
            "skill:scanner", "Scanner",
            dependencies=["skill:parser", "skill:validator"],
        )
        node = graph._nodes["skill:scanner"]
        assert "skill:parser" in node["dependencies"]
        assert "skill:validator" in node["dependencies"]

    def test_add_node_overwrites_existing(self):
        """add_node 更新已存在节点。"""
        graph = CapabilityEvolutionGraph()
        graph.add_node("skill:x", "Old Name", score=0.3)
        graph.add_node("skill:x", "New Name", score=0.9)
        node = graph._nodes["skill:x"]
        assert node["name"] == "New Name"
        assert node["score"] == 0.9

    # ── Edge Tests ──────────────────────────────────────────────────────

    def test_add_edge(self):
        """add_edge 在 _edges 列表中添加带时间戳的边。"""
        graph = CapabilityEvolutionGraph()
        graph.add_node("skill:a", "Skill A")
        graph.add_node("skill:b", "Skill B")
        graph.add_edge("skill:a", "skill:b", "adopted")
        assert len(graph._edges) == 1
        edge = graph._edges[0]
        assert edge["from"] == "skill:a"
        assert edge["to"] == "skill:b"
        assert edge["type"] == "adopted"
        assert "timestamp" in edge

    def test_add_multiple_edges(self):
        """支持多条边的添加。"""
        graph = CapabilityEvolutionGraph()
        for i in range(3):
            graph.add_edge(f"from_{i}", f"to_{i}", "upgraded")
        assert len(graph._edges) == 3

    # ── Export Tests ────────────────────────────────────────────────────

    def test_export_json_contains_nodes_and_edges(self):
        """export_json 返回包含 nodes、edges 和 metadata 的字典。"""
        graph = CapabilityEvolutionGraph()
        graph.add_node("skill:x", "Skill X", risk="high")
        graph.add_edge("skill:x", "skill:y", "deprecated")

        exported = graph.export_json()
        assert "nodes" in exported
        assert "edges" in exported
        assert "metadata" in exported
        assert len(exported["nodes"]) == 1
        assert len(exported["edges"]) == 1
        assert exported["nodes"][0]["name"] == "Skill X"
        assert exported["metadata"]["node_count"] == 1
        assert exported["metadata"]["edge_count"] == 1

    def test_export_json_empty_graph(self):
        """空图的 export_json 返回空列表和零计数。"""
        graph = CapabilityEvolutionGraph()
        exported = graph.export_json()
        assert exported["nodes"] == []
        assert exported["edges"] == []
        assert exported["metadata"]["node_count"] == 0

    # ── Registry Import Tests ───────────────────────────────────────────

    def test_build_from_registry(self):
        """build_from_registry 从 registry 和 tracker 构建图。"""
        graph = CapabilityEvolutionGraph()

        class MockRegistry:
            @staticmethod
            def all_skills():
                return {
                    "code_scanner": {"name": "Code Scanner"},
                    "risk_assessor": {"name": "Risk Assessor"},
                }

        class MockTracker:
            @staticmethod
            def get_recent_events(limit: int = 100):
                return [
                    {"from": "skill:code_scanner", "to": "skill:risk_assessor", "type": "adopted"},
                ]

        graph.build_from_registry(MockRegistry(), MockTracker())
        assert "skill:code_scanner" in graph._nodes
        assert "skill:risk_assessor" in graph._nodes
        assert graph._nodes["skill:code_scanner"]["name"] == "code_scanner"
        assert len(graph._edges) == 1
        assert graph._edges[0]["from"] == "skill:code_scanner"
        assert graph._edges[0]["type"] == "adopted"

    def test_build_from_registry_without_tracker(self):
        """当 tracker 没有 get_recent_events 时优雅降级。"""
        graph = CapabilityEvolutionGraph()

        class MockRegistry:
            @staticmethod
            def all_skills():
                return {"greeter": {"name": "Greeter"}}

        # Tracker without get_recent_events
        class BareTracker:
            pass

        graph.build_from_registry(MockRegistry(), BareTracker())
        assert "skill:greeter" in graph._nodes
        assert len(graph._edges) == 0

    # ── Timeline Tests ──────────────────────────────────────────────────

    def test_timeline_for_unknown_capability_returns_empty(self):
        """未知能力的 timeline 返回空列表。"""
        graph = CapabilityEvolutionGraph()
        assert graph.timeline("skill:nonexistent") == []

    def test_timeline_returns_related_edges(self):
        """timeline 返回能力相关的所有边（from 和 to）。"""
        graph = CapabilityEvolutionGraph()
        graph.add_edge("skill:a", "skill:b", "adopted")
        graph.add_edge("skill:b", "skill:c", "upgraded")
        graph.add_edge("skill:d", "skill:a", "deprecated")

        timeline_a = graph.timeline("skill:a")
        assert len(timeline_a) == 2  # as from (edge 1) and as to (edge 3)

        timeline_c = graph.timeline("skill:c")
        assert len(timeline_c) == 1  # only as to (edge 2)
        assert timeline_c[0]["from"] == "skill:b"
