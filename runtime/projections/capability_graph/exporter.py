"""CapabilityGraph v1.0 — 导出器

仅支持 JSON 和 DOT 格式。
DOT 输出可直接被 Graphviz 渲染。
"""

from __future__ import annotations

import json

from runtime.projections.capability_graph.models import CapabilityGraph

# ── 节点类型 → DOT 样式 ────────────────────────────────────────────

NODE_STYLES: dict[str, dict[str, str]] = {
    "trace":      {"shape": "box",     "color": "#4A90D9", "fontcolor": "#FFFFFF", "style": "filled"},
    "load":       {"shape": "ellipse", "color": "#50C878", "fontcolor": "#FFFFFF", "style": "filled"},
    "semantic":   {"shape": "ellipse", "color": "#FF8C00", "fontcolor": "#FFFFFF", "style": "filled"},
    "validate":   {"shape": "ellipse", "color": "#9370DB", "fontcolor": "#FFFFFF", "style": "filled"},
    "schedule":   {"shape": "ellipse", "color": "#20B2AA", "fontcolor": "#FFFFFF", "style": "filled"},
    "govern":     {"shape": "ellipse", "color": "#DC143C", "fontcolor": "#FFFFFF", "style": "filled"},
    "log":        {"shape": "ellipse", "color": "#696969", "fontcolor": "#FFFFFF", "style": "filled"},
}

EDGE_STYLES: dict[str, dict[str, str]] = {
    "causal_next":      {"color": "#333333", "style": "solid",  "arrowhead": "normal"},
    "same_trace":       {"color": "#AAAAAA", "style": "dashed", "arrowhead": "open"},
    "stage_transition": {"color": "#FF6600", "style": "bold",   "arrowhead": "vee"},
}


def _dot_label(node_id: str, graph: CapabilityGraph) -> str:
    """生成 DOT 节点标签。"""
    node = graph.get_node(node_id)
    if not node:
        return node_id

    parts = []
    # 第一行: ID
    short_id = node_id.split(":")[-1] if ":" in node_id else node_id
    parts.append(f"<B>{short_id}</B>")

    # 第二行: 类型
    parts.append(f"<I>{node.type}</I>")

    # 第三行: payload 摘要
    payload = node.metadata.get("payload", {})
    if isinstance(payload, dict):
        keys = list(payload.keys())
        if keys:
            parts.append(f"[{', '.join(keys[:4])}{'...' if len(keys) > 4 else ''}]")

    text = "<BR/>".join(parts)
    return f"<{text}>"


def export_graph(graph: CapabilityGraph, format: str = "json",
                 max_nodes: int = 200) -> str:
    """导出图。

    Args:
        graph: 要导出的图。
        format: "json" 或 "dot"。
        max_nodes: DOT 导出最大节点数（默认 200）。

    Returns:
        格式化的字符串输出。
    """
    if format == "json":
        return _export_json(graph)
    elif format == "dot":
        return _export_dot(graph, max_nodes)
    else:
        raise ValueError(f"不支持的导出格式: {format}，仅支持 json / dot")


# ── JSON 导出 ──────────────────────────────────────────────────────


def _export_json(graph: CapabilityGraph) -> str:
    """JSON 格式导出。"""
    nodes_json = {}
    for nid, node in graph.nodes.items():
        nodes_json[nid] = {
            "id": node.id,
            "type": node.type,
            "ref_event_id": node.ref_event_id,
            "metadata": node.metadata,
        }

    edges_json = []
    for edge in graph.edges:
        edges_json.append({
            "source": edge.source_id,
            "target": edge.target_id,
            "relation": edge.relation_type,
            "metadata": edge.metadata,
        })

    return json.dumps({
        "version": "1.0",
        "metadata": graph.metadata,
        "nodes": nodes_json,
        "edges": edges_json,
    }, ensure_ascii=False, indent=2)


# ── DOT 导出 ───────────────────────────────────────────────────────


def _export_dot(graph: CapabilityGraph, max_nodes: int = 200) -> str:
    """DOT 格式导出 — 可直接被 Graphviz 渲染。"""
    lines = [
        "digraph DVexaCapabilityGraph {",
        "  rankdir=LR;",
        "  splines=polyline;",
        "  overlap=false;",
        "  fontname=\"Helvetica\";",
        "",
        "  // ===== 图元数据 ===== ",
        f"  label=\"DVexa Capability Graph v1.0\\n(graph.metadata)\";",
        f"  fontsize=16;",
        "",
        "  // ===== 节点样式 ===== ",
    ]

    # 输出节点样式定义
    seen_styles = set()
    for node in graph.nodes.values():
        style = NODE_STYLES.get(node.type, {})
        if node.type not in seen_styles:
            lines.append(
                f"  node [shape={style.get('shape', 'ellipse')},"
                f" style={style.get('style', 'filled')},"
                f" fillcolor={style.get('color', '#CCCCCC')},"
                f" fontcolor={style.get('fontcolor', '#000000')}];"
            )
            seen_styles.add(node.type)

    lines.append("")

    # 输出节点
    node_ids = list(graph.nodes.keys())
    if len(node_ids) > max_nodes:
        lines.append(f"  // 节点数 {len(node_ids)} 超过上限 {max_nodes}，已截断")
        node_ids = node_ids[:max_nodes]
        lines.append(f"  // 显示前 {max_nodes} 个节点")

    for nid in node_ids:
        label = _dot_label(nid, graph)
        lines.append(f'  "{nid}" [label={label}];')

    lines.append("")
    lines.append("  // ===== 边 ===== ")

    # 输出边
    edge_count = 0
    for edge in graph.edges:
        if edge.source_id not in graph.nodes or edge.target_id not in graph.nodes:
            continue
        style = EDGE_STYLES.get(edge.relation_type, {})
        attrs = f"color={style.get('color', '#000000')}, style={style.get('style', 'solid')}, arrowhead={style.get('arrowhead', 'normal')}"
        lines.append(f'  "{edge.source_id}" -> "{edge.target_id}" [{attrs}];')
        edge_count += 1

    lines.append("")
    lines.append("  // ===== 图例 ===== ")
    lines.append("  subgraph cluster_legend {")
    lines.append('    label="图例";')
    lines.append("    fontsize=12;")
    lines.append("    style=dashed;")
    lines.append("    color=grey;")

    for ntype, nstyle in NODE_STYLES.items():
        lines.append(
            f'    legend_{ntype} [label="{ntype}", shape={nstyle["shape"]},'
            f' style=filled, fillcolor={nstyle["color"]}, fontcolor=white];'
        )

    for etype, estyle in EDGE_STYLES.items():
        lines.append(
            f'    legend_{etype}_a [label="", color=white];'
        )
        lines.append(
            f'    legend_{etype}_a -> legend_{etype}_b [label=" {etype}",'
            f' color={estyle["color"]}, style={estyle["style"]},'
            f' arrowhead={estyle["arrowhead"]}];'
        )

    lines.append("  }")
    lines.append("}")

    return "\n".join(lines)
