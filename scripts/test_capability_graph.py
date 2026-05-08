#!/usr/bin/env python3
"""CapabilityGraph v1.0 — 集成冒烟测试

从 EventStore → 构建图 → 查询 → 导出 的 E2E 验证。
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.event import EventStore, Event
from runtime.projections.capability_graph import (
    CapabilityGraphBuilder,
    query_capability,
    find_dependency_chain,
    simulate_impact,
    export_graph,
)


def seed_test_data(store: EventStore):
    """注入测试事件到 EventStore。"""
    t = time.time()

    # Trace 1: 正常执行流水线
    trace_1_events = [
        Event(trace_id="grf-t1", stage="load", event_type="info",
              payload={"target": "analyze system", "intent": "analysis"}, timestamp=t),
        Event(trace_id="grf-t1", stage="semantic", event_type="decision",
              payload={"intent": "analysis", "risk_score": 0.05, "threat_type": "none"},
              timestamp=t + 0.1),
        Event(trace_id="grf-t1", stage="validate", event_type="decision",
              payload={"passed": True, "risk_score": 0.05, "phases": ["identity", "intent", "safety"]},
              timestamp=t + 0.2),
        Event(trace_id="grf-t1", stage="schedule", event_type="decision",
              payload={"action": "approve", "result": "approved", "final_state": "APPROVED"},
              timestamp=t + 0.3),
        Event(trace_id="grf-t1", stage="govern", event_type="info",
              payload={"skill_count": 5, "stability": 0.95},
              timestamp=t + 0.4),
        Event(trace_id="grf-t1", stage="log", event_type="info",
              payload={"message": "execution complete"},
              timestamp=t + 0.5),
    ]
    for evt in trace_1_events:
        store.append(evt)

    # Trace 2: 含风险的对抗输入
    trace_2_events = [
        Event(trace_id="grf-t2", stage="load", event_type="info",
              payload={"target": "bypass security", "intent": "manipulation"}, timestamp=t + 1.0),
        Event(trace_id="grf-t2", stage="semantic", event_type="risk",
              payload={"threat_type": "control_bypass", "risk_score": 0.9,
                       "intent": "manipulation", "governance_impact": "block"},
              timestamp=t + 1.1),
        Event(trace_id="grf-t2", stage="validate", event_type="decision",
              payload={"passed": False, "risk_score": 0.9, "phases": ["identity", "intent", "safety"]},
              timestamp=t + 1.2),
        Event(trace_id="grf-t2", stage="schedule", event_type="decision",
              payload={"action": "reject", "result": "rejected", "final_state": "REJECTED"},
              timestamp=t + 1.3),
    ]
    for evt in trace_2_events:
        store.append(evt)

    print(f"  ✓ 注入 2 个 trace，共 {len(trace_1_events) + len(trace_2_events)} 个事件")
    return trace_1_events, trace_2_events


def test_build_graph(builder):
    """测试图构建。"""
    print("\n  ── 构建图 ──")

    # 全量图
    full = builder.build_graph()
    assert full.node_count > 0
    assert full.edge_count > 0
    print(f"  ✓ 全量图: {full.node_count} 节点, {full.edge_count} 边, "
          f"{full.metadata['trace_count']} trace")

    # 单 trace 图
    t1 = builder.build_execution_graph("grf-t1")
    t2 = builder.build_execution_graph("grf-t2")
    print(f"  ✓ grf-t1: {t1.node_count} 节点, {t1.edge_count} 边")
    print(f"  ✓ grf-t2: {t2.node_count} 节点, {t2.edge_count} 边")

    # 节点类型分布
    by_type = {}
    for n in full.nodes.values():
        by_type[n.type] = by_type.get(n.type, 0) + 1
    print(f"  ✓ 节点类型分布: {by_type}")

    return full, t1, t2


def test_queries(full_graph):
    """测试查询操作。"""
    print("\n  ── 查询操作 ──")

    # 1. query_capability: 第一个事件
    nid = "grf-t1:evt:0"
    sub = query_capability(full_graph, nid)
    assert sub.node_count >= 1
    print(f"  ✓ query_capability({nid}): {sub.node_count} 节点, {sub.edge_count} 边")

    # 2. find_dependency_chain: 中间事件 → 回溯到起点
    chain = find_dependency_chain(full_graph, "grf-t1:evt:3")
    ordered = chain.metadata.get("ordered_chain", [])
    assert len(ordered) >= 2
    print(f"  ✓ find_dependency_chain(evt:3): {ordered}")

    # 3. simulate_impact: 移除风险事件
    impact = simulate_impact(full_graph, "grf-t2:evt:1")
    assert "total_downstream" in impact
    print(f"  ✓ simulate_impact(grf-t2:evt:1): {impact['total_downstream']} 下游, "
          f"severity={impact['severity']}")

    # 4. simulate_impact: 叶节点
    impact2 = simulate_impact(full_graph, "grf-t1:evt:5")
    assert impact2["total_downstream"] == 0
    print(f"  ✓ simulate_impact(叶节点): 无下游 → severity=none")


def test_replay(store):
    """测试从 EventStore 重建。"""
    print("\n  ── EventStore 重建 ──")

    events = []
    for tid in store.list_traces():
        events.extend(store.read_by_trace(tid))

    g = CapabilityGraphBuilder.reconstruct_from_events(events)
    assert g.node_count > 0
    assert g.metadata.get("reconstructed") is True
    print(f"  ✓ 从 {len(events)} 个事件重建: {g.node_count} 节点, {g.edge_count} 边")


def test_export(full_graph):
    """测试导出。"""
    print("\n  ── 导出 ──")

    json_out = export_graph(full_graph, format="json")
    import json
    data = json.loads(json_out)
    print(f"  ✓ JSON 导出: {len(data['nodes'])} 节点, {len(data['edges'])} 边")

    dot_out = export_graph(full_graph, format="dot", max_nodes=30)
    dot_lines = dot_out.strip().split("\n")
    print(f"  ✓ DOT 导出: {len(dot_lines)} 行")

    # 尝试渲染 DOT（如果安装了 graphviz）
    try:
        import subprocess
        proc = subprocess.run(
            ["dot", "-Tpng", "-o", "/tmp/capability_graph_test.png"],
            input=dot_out, capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            print(f"  ✓ Graphviz 渲染: /tmp/capability_graph_test.png")
        else:
            print(f"  - Graphviz 渲染跳过 (返回码 {proc.returncode})")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"  - Graphviz 未安装，跳过渲染")


def test_determinism(store):
    """测试确定性。"""
    print("\n  ── 确定性验证 ──")

    builder = CapabilityGraphBuilder(store)
    g1 = builder.build_graph()
    g2 = builder.build_graph()

    n1 = set(g1.nodes.keys())
    n2 = set(g2.nodes.keys())
    assert n1 == n2, f"节点不一致: {n1.symmetric_difference(n2)}"

    e1 = {(e.source_id, e.target_id, e.relation_type) for e in g1.edges}
    e2 = {(e.source_id, e.target_id, e.relation_type) for e in g2.edges}
    assert e1 == e2, f"边不一致: {e1.symmetric_difference(e2)}"

    print(f"  ✓ 两次构建结果完全一致 ({len(n1)} 节点, {len(e1)} 边)")


def main():
    print("=" * 60)
    print("  CapabilityGraph v1.0 — 集成冒烟测试")
    print("=" * 60)

    start = time.time()

    # 准备 EventStore
    print("\n  ── 准备数据 ──")
    store = EventStore()
    seed_test_data(store)

    # 构建
    builder = CapabilityGraphBuilder(store)
    full_graph, t1, t2 = test_build_graph(builder)

    # 查询
    test_queries(full_graph)

    # 回放
    test_replay(store)

    # 导出
    test_export(full_graph)

    # 确定性
    test_determinism(store)

    # 汇总
    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  集成测试完成")
    print(f"  耗时: {elapsed:.3f}s")
    print(f"  节点数: {full_graph.node_count}")
    print(f"  边数:   {full_graph.edge_count}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
