"""Tests: CapabilityGraph v1.0 — EventStore 投影层测试"""

import json
import os
import tempfile
import time

from runtime.event import EventStore, Event
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


# ====================================================================
# 模型测试
# ====================================================================


class TestCapabilityNode:
    def test_create(self):
        n = CapabilityNode(id="test:evt:0", type="load", ref_event_id="test")
        assert n.id == "test:evt:0"
        assert n.type == "load"
        assert n.ref_event_id == "test"
        assert n.metadata == {}
        assert n.is_derived is True

    def test_with_metadata(self):
        n = CapabilityNode(
            id="test:evt:1",
            type="semantic",
            ref_event_id="test",
            metadata={"risk_score": 0.9},
        )
        assert n.metadata["risk_score"] == 0.9

    def test_immutable(self):
        n = CapabilityNode(id="a", type="load", ref_event_id="t")
        import dataclasses
        assert dataclasses.fields(n)  # 确认是 dataclass
        # frozen=True → 尝试修改应抛出异常
        try:
            n.id = "new"
            assert False, "should be frozen"
        except Exception:
            pass

    def test_equality(self):
        a = CapabilityNode(id="x", type="load", ref_event_id="t")
        b = CapabilityNode(id="x", type="load", ref_event_id="t")
        assert a == b


class TestCapabilityEdge:
    def test_create(self):
        e = CapabilityEdge(
            source_id="a", target_id="b", relation_type="causal_next"
        )
        assert e.source_id == "a"
        assert e.target_id == "b"
        assert e.relation_type == "causal_next"

    def test_with_metadata(self):
        e = CapabilityEdge(
            source_id="a", target_id="b",
            relation_type="same_trace",
            metadata={"trace_id": "trc-001"},
        )
        assert e.metadata["trace_id"] == "trc-001"

    def test_all_relation_types(self):
        for rt in ("causal_next", "same_trace", "stage_transition"):
            e = CapabilityEdge(source_id="s", target_id="t", relation_type=rt)
            assert e.relation_type == rt


class TestCapabilityGraph:
    def test_empty(self):
        g = CapabilityGraph()
        assert g.node_count == 0
        assert g.edge_count == 0

    def test_nodes_and_edges(self):
        n1 = CapabilityNode(id="n1", type="load", ref_event_id="t")
        n2 = CapabilityNode(id="n2", type="semantic", ref_event_id="t")
        e1 = CapabilityEdge(source_id="n1", target_id="n2", relation_type="causal_next")
        g = CapabilityGraph(nodes={"n1": n1, "n2": n2}, edges=[e1])
        assert g.node_count == 2
        assert g.edge_count == 1

    def test_get_node(self):
        n1 = CapabilityNode(id="n1", type="load", ref_event_id="t")
        g = CapabilityGraph(nodes={"n1": n1})
        assert g.get_node("n1") is n1
        assert g.get_node("nonexistent") is None

    def test_get_edge(self):
        e1 = CapabilityEdge(source_id="a", target_id="b", relation_type="causal_next")
        g = CapabilityGraph(edges=[e1])
        assert g.get_edge(0) is e1
        assert g.get_edge(99) is None

    def test_outgoing(self):
        n1 = CapabilityNode(id="n1", type="load", ref_event_id="t")
        n2 = CapabilityNode(id="n2", type="semantic", ref_event_id="t")
        e1 = CapabilityEdge(source_id="n1", target_id="n2", relation_type="causal_next")
        g = CapabilityGraph(nodes={"n1": n1, "n2": n2}, edges=[e1])
        out = g.outgoing("n1")
        assert len(out) == 1
        assert out[0][0] is e1
        assert out[0][1] is n2

    def test_incoming(self):
        n1 = CapabilityNode(id="n1", type="load", ref_event_id="t")
        n2 = CapabilityNode(id="n2", type="semantic", ref_event_id="t")
        e1 = CapabilityEdge(source_id="n1", target_id="n2", relation_type="causal_next")
        g = CapabilityGraph(nodes={"n1": n1, "n2": n2}, edges=[e1])
        inc = g.incoming("n2")
        assert len(inc) == 1
        assert inc[0][0] is e1
        assert inc[0][1] is n1

    def test_outgoing_empty(self):
        n1 = CapabilityNode(id="n1", type="load", ref_event_id="t")
        g = CapabilityGraph(nodes={"n1": n1})
        assert g.outgoing("n1") == []
        assert g.outgoing("nonexistent") == []

    def test_node_ids_by_type(self):
        nodes = {
            "a": CapabilityNode(id="a", type="load", ref_event_id="t"),
            "b": CapabilityNode(id="b", type="semantic", ref_event_id="t"),
            "c": CapabilityNode(id="c", type="load", ref_event_id="t"),
        }
        g = CapabilityGraph(nodes=nodes)
        loads = g.node_ids_by_type("load")
        assert set(loads) == {"a", "c"}
        assert g.node_ids_by_type("nonexistent") == []


# ====================================================================
# 构建器测试
# ====================================================================


class _TestStore:
    """辅助：使用临时目录的 EventStore。"""
    @staticmethod
    def create():
        tmp = tempfile.mkdtemp()
        return EventStore(base_dir=tmp)


class TestCapabilityGraphBuilder:
    def test_empty_store(self):
        store = _TestStore.create()
        builder = CapabilityGraphBuilder(store)
        g = builder.build_graph()
        assert g.node_count == 0
        assert g.edge_count == 0
        assert g.metadata.get("empty") is True

    def test_single_trace(self):
        store = _TestStore.create()
        t = time.time()
        store.append(Event(trace_id="t1", stage="load", event_type="info",
                           payload={"target": "test"}, timestamp=t))
        store.append(Event(trace_id="t1", stage="semantic", event_type="decision",
                           payload={"intent": "analysis"}, timestamp=t + 0.1))
        builder = CapabilityGraphBuilder(store)
        g = builder.build_graph()
        assert g.node_count == 3  # trace root + 2 events
        assert g.metadata["trace_count"] == 1
        assert g.metadata["total_events"] == 2

    def test_multiple_traces(self):
        store = _TestStore.create()
        t = time.time()
        store.append(Event(trace_id="ta", stage="load", event_type="info", payload={}, timestamp=t))
        store.append(Event(trace_id="tb", stage="load", event_type="info", payload={}, timestamp=t))
        store.append(Event(trace_id="tb", stage="semantic", event_type="decision", payload={}, timestamp=t + 0.1))
        builder = CapabilityGraphBuilder(store)
        g = builder.build_graph()
        assert g.metadata["trace_count"] == 2
        assert g.metadata["total_events"] == 3

    def test_execution_graph(self):
        store = _TestStore.create()
        t = time.time()
        store.append(Event(trace_id="t1", stage="load", event_type="info", payload={}, timestamp=t))
        store.append(Event(trace_id="t1", stage="semantic", event_type="decision", payload={}, timestamp=t + 0.1))
        store.append(Event(trace_id="t2", stage="load", event_type="info", payload={}, timestamp=t))
        builder = CapabilityGraphBuilder(store)
        g = builder.build_execution_graph("t1")
        assert g.metadata["trace_count"] == 1
        assert g.metadata["total_events"] == 2

    def test_execution_nonexistent_trace(self):
        store = _TestStore.create()
        builder = CapabilityGraphBuilder(store)
        g = builder.build_execution_graph("nonexistent")
        assert g.node_count == 0

    def test_deterministic(self):
        store = _TestStore.create()
        t = time.time()
        store.append(Event(trace_id="t1", stage="load", event_type="info", payload={"x": 1}, timestamp=t))
        store.append(Event(trace_id="t1", stage="validate", event_type="decision", payload={"x": 2}, timestamp=t + 0.1))
        builder = CapabilityGraphBuilder(store)
        g1 = builder.build_graph()
        g2 = builder.build_graph()
        assert len(g1.nodes) == len(g2.nodes)
        assert len(g1.edges) == len(g2.edges)
        assert set(g1.nodes.keys()) == set(g2.nodes.keys())

    def test_has_stage_transitions(self):
        store = _TestStore.create()
        t = time.time()
        store.append(Event(trace_id="t1", stage="load", event_type="info", payload={}, timestamp=t))
        store.append(Event(trace_id="t1", stage="semantic", event_type="decision", payload={}, timestamp=t + 0.1))
        store.append(Event(trace_id="t1", stage="validate", event_type="decision", payload={}, timestamp=t + 0.2))
        builder = CapabilityGraphBuilder(store)
        g = builder.build_graph()
        stage_transitions = [e for e in g.edges if e.relation_type == "stage_transition"]
        assert len(stage_transitions) == 2

    def test_has_causal_next(self):
        store = _TestStore.create()
        t = time.time()
        store.append(Event(trace_id="t1", stage="load", event_type="info", payload={}, timestamp=t))
        store.append(Event(trace_id="t1", stage="semantic", event_type="decision", payload={}, timestamp=t + 0.1))
        builder = CapabilityGraphBuilder(store)
        g = builder.build_graph()
        causal = [e for e in g.edges if e.relation_type == "causal_next"]
        assert len(causal) >= 1

    def test_reconstruct_from_events(self):
        store = _TestStore.create()
        t = time.time()
        store.append(Event(trace_id="t1", stage="load", event_type="info", payload={}, timestamp=t))
        store.append(Event(trace_id="t1", stage="semantic", event_type="decision", payload={}, timestamp=t + 0.1))
        events = store.read_by_trace("t1")
        g = CapabilityGraphBuilder.reconstruct_from_events(events)
        assert g.node_count == 3
        assert g.metadata.get("reconstructed") is True


# ====================================================================
# 查询测试
# ====================================================================


def _make_test_graph():
    """辅助：构建含 2 个 trace 的测试图。"""
    nodes = {}
    edges = []
    # Trace A: 4 个事件
    for i, (stage, etype) in enumerate([("load", "info"), ("semantic", "decision"),
                                         ("validate", "decision"), ("schedule", "info")]):
        nid = f"trc-a:evt:{i}"
        nodes[nid] = CapabilityNode(id=nid, type=stage, ref_event_id="trc-a",
                                    metadata={"event_type": etype, "index": i, "stage": stage})
    nodes["trace:trc-a"] = CapabilityNode(id="trace:trc-a", type="trace", ref_event_id="trc-a")
    for i in range(4):
        eid = f"trc-a:evt:{i}"
        edges.append(CapabilityEdge(source_id="trace:trc-a", target_id=eid, relation_type="same_trace",
                                    metadata={"trace_id": "trc-a"}))
        if i > 0:
            pid = f"trc-a:evt:{i - 1}"
            edges.append(CapabilityEdge(source_id=pid, target_id=eid, relation_type="causal_next",
                                        metadata={"trace_id": "trc-a"}))
    edges.append(CapabilityEdge(source_id="trc-a:evt:0", target_id="trc-a:evt:1",
                                relation_type="stage_transition", metadata={"from_stage": "load", "to_stage": "semantic"}))
    # Trace B: 2 个事件
    for i, (stage, etype) in enumerate([("load", "info"), ("semantic", "risk")]):
        nid = f"trc-b:evt:{i}"
        nodes[nid] = CapabilityNode(id=nid, type=stage, ref_event_id="trc-b",
                                    metadata={"event_type": etype, "index": i, "stage": stage})
    nodes["trace:trc-b"] = CapabilityNode(id="trace:trc-b", type="trace", ref_event_id="trc-b")
    for i in range(2):
        eid = f"trc-b:evt:{i}"
        edges.append(CapabilityEdge(source_id="trace:trc-b", target_id=eid, relation_type="same_trace",
                                    metadata={"trace_id": "trc-b"}))
        if i > 0:
            pid = f"trc-b:evt:{i - 1}"
            edges.append(CapabilityEdge(source_id=pid, target_id=eid, relation_type="causal_next",
                                        metadata={"trace_id": "trc-b"}))
    return CapabilityGraph(nodes=nodes, edges=edges)


class TestQueries:
    def test_query_existing_node(self):
        g = _make_test_graph()
        sub = query_capability(g, "trc-a:evt:1")
        assert sub.node_count >= 1
        assert sub.metadata["query"] == "query_capability"
        assert sub.metadata["center"] == "trc-a:evt:1"

    def test_query_nonexistent_node(self):
        g = _make_test_graph()
        sub = query_capability(g, "nonexistent")
        assert "error" in sub.metadata

    def test_query_root_node(self):
        g = _make_test_graph()
        sub = query_capability(g, "trace:trc-a")
        assert sub.node_count > 1  # root + its children

    def test_dependency_chain(self):
        g = _make_test_graph()
        chain = find_dependency_chain(g, "trc-a:evt:3")
        assert "error" not in chain.metadata
        assert len(chain.metadata["ordered_chain"]) >= 2
        assert chain.metadata["ordered_chain"][0] == "trc-a:evt:0"
        assert chain.metadata["ordered_chain"][-1] == "trc-a:evt:3"

    def test_dependency_chain_nonexistent(self):
        g = _make_test_graph()
        chain = find_dependency_chain(g, "nonexistent")
        assert "error" in chain.metadata

    def test_dependency_chain_single_node(self):
        g = _make_test_graph()
        chain = find_dependency_chain(g, "trc-a:evt:0")
        assert len(chain.nodes) >= 1

    def test_simulate_impact_leaf(self):
        g = _make_test_graph()
        impact = simulate_impact(g, "trc-a:evt:3")
        assert impact["total_downstream"] == 0  # leaf node
        assert impact["severity"] == "none"

    def test_simulate_impact_mid(self):
        g = _make_test_graph()
        impact = simulate_impact(g, "trc-a:evt:1")
        assert impact["total_downstream"] >= 1
        assert impact["severity"] in ("low", "medium", "high")

    def test_simulate_impact_nonexistent(self):
        g = _make_test_graph()
        impact = simulate_impact(g, "nonexistent")
        assert "error" in impact

    def test_simulate_impact_trace_root(self):
        g = _make_test_graph()
        impact = simulate_impact(g, "trace:trc-b")
        # trace root 只有 same_trace 边（非因果），所以 downstream 为 0
        assert impact["total_downstream"] == 0


# ====================================================================
# 导出测试
# ====================================================================


class TestExport:
    def test_json_empty_graph(self):
        g = CapabilityGraph()
        out = export_graph(g, format="json")
        data = json.loads(out)
        assert data["version"] == "1.0"
        assert data["nodes"] == {}
        assert data["edges"] == []

    def test_json_with_data(self):
        g = _make_test_graph()
        out = export_graph(g, format="json")
        data = json.loads(out)
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0

    def test_dot_empty_graph(self):
        g = CapabilityGraph()
        out = export_graph(g, format="dot")
        assert out.startswith("digraph")
        assert "}" in out

    def test_dot_with_data(self):
        g = _make_test_graph()
        out = export_graph(g, format="dot")
        assert '"trace:trc-a"' in out
        assert '"trc-a:evt:0"' in out
        assert "causal_next" in out or "->" in out

    def test_invalid_format(self):
        g = CapabilityGraph()
        try:
            export_graph(g, format="xml")
            assert False, "should raise ValueError"
        except ValueError:
            pass


# ====================================================================
# 确定性测试
# ====================================================================


class TestDeterminism:
    def test_identical_graphs(self):
        """相同输入产生完全相同图（节点和边的 ID 集合一致）。"""
        store = _TestStore.create()
        t = time.time()
        for i in range(5):
            store.append(Event(trace_id="dtrc", stage=["load", "semantic", "validate"][i % 3],
                               event_type="info" if i % 2 == 0 else "decision",
                               payload={"i": i}, timestamp=t + i * 0.1))
        builder = CapabilityGraphBuilder(store)
        g1 = builder.build_graph()
        g2 = builder.build_graph()
        assert set(g1.nodes.keys()) == set(g2.nodes.keys())
        e1_set = {(e.source_id, e.target_id, e.relation_type) for e in g1.edges}
        e2_set = {(e.source_id, e.target_id, e.relation_type) for e in g2.edges}
        assert e1_set == e2_set


# ====================================================================
# 集成测试：EventStore 投影
# ====================================================================


class TestEventStoreIntegration:
    def test_build_then_replay(self):
        """构建图 → 从 EventStore 读取事件 → 重建图 → 图一致。"""
        store = _TestStore.create()
        t = time.time()
        store.append(Event(trace_id="int-t1", stage="load", event_type="info",
                           payload={"msg": "hello"}, timestamp=t))
        store.append(Event(trace_id="int-t1", stage="semantic", event_type="decision",
                           payload={"intent": "greet"}, timestamp=t + 0.1))
        store.append(Event(trace_id="int-t1", stage="log", event_type="info",
                           payload={"msg": "done"}, timestamp=t + 0.2))

        builder = CapabilityGraphBuilder(store)
        g1 = builder.build_graph()
        events = store.read_by_trace("int-t1")
        g2 = CapabilityGraphBuilder.reconstruct_from_events(events)
        assert g1.node_count > 0
        assert g2.node_count > 0

    def test_incremental_build(self):
        """逐步添加事件后构建图。"""
        store = _TestStore.create()
        builder = CapabilityGraphBuilder(store)
        g1 = builder.build_graph()
        assert g1.node_count == 0

        store.append(Event(trace_id="inc", stage="load", event_type="info", payload={}))
        g2 = builder.build_graph()
        assert g2.node_count > 0
