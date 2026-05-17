"""Capability Evolution Graph — 能力演化 DAG

追踪能力之间的演化关系（adopted|deprecated|upgraded|downgraded）。
纯数据结构：节点存储能力元数据，边存储演化事件。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class CapabilityEvolutionGraph:
    """能力演化图 — 有向无环图 (DAG)。

    节点表示能力（skill/governance module/pattern），
    边表示演化关系：adopted（采纳）、deprecated（弃用）、
    upgraded（升级）、downgraded（降级）。

    可通过 build_from_registry() 从 CapabilityRegistry +
    EvolutionTracker 自动构建初始图。
    """

    def __init__(self):
        self._nodes: dict[str, dict] = {}
        self._edges: list[dict] = []

    # ── Node Operations ─────────────────────────────────────────────────

    def add_node(self, capability_id: str, name: str, score: float = 0.0,
                 lifecycle: str = "active", risk: str = "low",
                 dependencies: list[str] | None = None) -> None:
        """添加或更新能力节点。

        Args:
            capability_id: 全局唯一能力 ID（如 "skill:code_scanner"）。
            name: 可读名称。
            score: 能力评分 0.0 ~ 1.0。
            lifecycle: 生命周期状态（active|deprecated|experimental）。
            risk: 风险等级（low|medium|high|critical）。
            dependencies: 依赖的能力 ID 列表。
        """
        self._nodes[capability_id] = {
            "capability_id": capability_id,
            "name": name,
            "score": score,
            "lifecycle": lifecycle,
            "risk": risk,
            "dependencies": dependencies or [],
        }

    # ── Edge Operations ─────────────────────────────────────────────────

    def add_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        """添加演化边。

        Args:
            from_id: 源能力 ID。
            to_id: 目标能力 ID。
            edge_type: 演化类型（adopted|deprecated|upgraded|downgraded）。
        """
        self._edges.append({
            "from": from_id,
            "to": to_id,
            "type": edge_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Registry Import ─────────────────────────────────────────────────

    def build_from_registry(self, registry, evolution_tracker) -> None:
        """从 CapabilityRegistry + EvolutionTracker 构建初始图。

        registry 和 evolution_tracker 是 duck-typed，分别需要：
            - registry.all_skills() -> dict[str, Any]
            - evolution_tracker.get_recent_events(limit=100) -> list[dict]
        """
        for name, skill_def in registry.all_skills().items():
            self.add_node(capability_id=f"skill:{name}", name=name)

        if hasattr(evolution_tracker, "get_recent_events"):
            for event in evolution_tracker.get_recent_events(limit=100):
                self.add_edge(
                    event.get("from"),
                    event.get("to"),
                    event.get("type", "adopted"),
                )

    # ── Export ──────────────────────────────────────────────────────────

    def export_json(self) -> dict:
        """导出完整 DAG 为 JSON（直接可序列化）。"""
        return {
            "nodes": list(self._nodes.values()),
            "edges": list(self._edges),
            "metadata": {
                "node_count": len(self._nodes),
                "edge_count": len(self._edges),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ── Timeline ────────────────────────────────────────────────────────

    def timeline(self, capability_id: str) -> list[dict]:
        """重建单个能力的时间线。

        返回与该能力相关的所有演化事件（作为 from 或 to）。
        """
        return [
            e for e in self._edges
            if e["from"] == capability_id or e["to"] == capability_id
        ]
