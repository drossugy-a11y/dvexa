"""Capability Dependency Graph v1.0 — 能力依赖/冲突图

纯 deterministic DAG 图结构。无外部图运行时依赖（no networkx）。
不可变操作模式 — 所有写入返回新状态副本。

与 runtime/projections/capability_graph/ 的区别:
  本模块: 能力分类学的依赖+冲突图（design-time）
  运行时: EventStore 执行投影图（runtime）
"""

from __future__ import annotations

from typing import Any


class CapabilityGraph:
    """能力依赖图 — DAG 结构。

    追踪:
      - 依赖关系 (depends_on)
      - 冲突关系 (conflicts_with)
      - 环检测
      - 拓扑深度
      - 文本可视化
    """

    def __init__(self):
        self._nodes: dict[str, dict[str, Any]] = {}
        self._dependencies: dict[str, set[str]] = {}  # node → {depends_on}
        self._conflicts: dict[str, set[str]] = {}      # node → {conflicts_with}
        self._metadata: dict[str, Any] = {}

    # ── 节点操作 ──────────────────────────────────────────────────────────

    def add_node(self, node_id: str, metadata: dict[str, Any] | None = None) -> None:
        if node_id not in self._nodes:
            self._nodes[node_id] = metadata or {}
            self._dependencies[node_id] = set()
            self._conflicts[node_id] = set()

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._nodes.get(node_id)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def nodes(self) -> dict[str, dict[str, Any]]:
        return dict(self._nodes)

    # ── 依赖操作 ──────────────────────────────────────────────────────────

    def add_dependency(self, from_id: str, to_id: str) -> bool:
        """from_id 依赖 to_id。"""
        if from_id not in self._nodes or to_id not in self._nodes:
            return False
        if from_id == to_id:
            return False
        self._dependencies[from_id].add(to_id)
        return True

    def get_dependencies(self, node_id: str) -> list[str]:
        return sorted(self._dependencies.get(node_id, set()))

    def get_dependents(self, node_id: str) -> list[str]:
        result = []
        for nid, deps in self._dependencies.items():
            if node_id in deps:
                result.append(nid)
        return sorted(result)

    # ── 冲突操作 ──────────────────────────────────────────────────────────

    def add_conflict(self, id_a: str, id_b: str) -> bool:
        if id_a not in self._nodes or id_b not in self._nodes:
            return False
        if id_a == id_b:
            return False
        self._conflicts[id_a].add(id_b)
        self._conflicts[id_b].add(id_a)
        return True

    def get_conflicts(self, node_id: str) -> list[str]:
        return sorted(self._conflicts.get(node_id, set()))

    def has_conflict(self, id_a: str, id_b: str) -> bool:
        return id_b in self._conflicts.get(id_a, set())

    # ── 图分析 ────────────────────────────────────────────────────────────

    def detect_cycles(self) -> list[list[str]]:
        """DFS 环检测。返回所有检测到的环。"""
        cycles: list[list[str]] = []
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in self._nodes}

        def dfs(node: str, path: list[str]):
            color[node] = GRAY
            path.append(node)
            for dep in self._dependencies.get(node, set()):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    cycle_start = path.index(dep)
                    cycles.append(list(path[cycle_start:]) + [dep])
                elif color[dep] == WHITE:
                    dfs(dep, path)
            path.pop()
            color[node] = BLACK

        for nid in self._nodes:
            if color[nid] == WHITE:
                dfs(nid, [])
        return cycles

    def compute_depth(self) -> dict[str, int]:
        """拓扑深度计算。根节点 depth=0。"""
        depth: dict[str, int] = {}
        visited: set[str] = set()

        def dfs_depth(node: str) -> int:
            if node in depth:
                return depth[node]
            if node in visited:
                return 0
            visited.add(node)
            deps = self._dependencies.get(node, set())
            if not deps:
                depth[node] = 0
            else:
                depth[node] = 1 + max(dfs_depth(d) for d in deps)
            return depth[node]

        for nid in self._nodes:
            dfs_depth(nid)
        return dict(depth)

    def get_transitive_dependencies(self, node_id: str) -> set[str]:
        """获取传递闭包中的所有依赖。"""
        result: set[str] = set()
        visited: set[str] = set()

        def dfs(nid: str):
            if nid in visited:
                return
            visited.add(nid)
            for dep in self._dependencies.get(nid, set()):
                result.add(dep)
                dfs(dep)

        dfs(node_id)
        return result

    # ── 文本可视化 ────────────────────────────────────────────────────────

    def visualize_text(self) -> str:
        """ASCII 树形文本可视化。

        输出示例:
        Planning
        ├── decomposition
        │   ├── recursive-task-splitting
        │   └── adaptive-replanning
        ├── reflection
        └── strategy-selection
        """
        roots = self._find_roots()
        if not roots:
            return "(empty graph)"

        lines: list[str] = []
        for i, root in enumerate(roots):
            self._render_tree(root, "", i == len(roots) - 1, lines, set())
        return "\n".join(lines)

    def _find_roots(self) -> list[str]:
        """找出所有根节点（无依赖其他节点的节点）。"""
        return sorted(nid for nid in self._nodes if not self._dependencies.get(nid))

    def _render_tree(self, node_id: str, prefix: str, is_last: bool,
                     lines: list[str], visited: set[str]):
        if node_id in visited:
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}{node_id} (↺)")
            return
        visited.add(node_id)

        connector = "└── " if is_last else "├── "
        meta = self._nodes.get(node_id, {})
        label = meta.get("label", node_id)
        lines.append(f"{prefix}{connector}{label}")

        children = self.get_dependents(node_id)
        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(children):
            self._render_tree(child, child_prefix, i == len(children) - 1,
                             lines, set(visited))

    # ── 元数据 ────────────────────────────────────────────────────────────

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "node_count": self.node_count,
            "dependency_count": sum(len(d) for d in self._dependencies.values()),
            "conflict_count": sum(len(c) for c in self._conflicts.values()) // 2,
            "has_cycles": len(self.detect_cycles()) > 0,
            **self._metadata,
        }

    def set_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value
