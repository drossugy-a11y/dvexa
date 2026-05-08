"""Capability Registry v1.0 — 统一能力注册中心

所有能力（skill、governance module、assimilation pattern、optimization module）
启动时自动注册到此注册中心。

只负责:
  - 注册和索引
  - 查询和筛选
  - 指标更新

不负责:
  - 执行决策
  - 自动修改 capability
  - 生命周期转换（由 SkillGovernor 负责）
"""

from __future__ import annotations

from typing import Any

from capabilities.taxonomy import (
    CapabilityNode,
    MaturityLevel,
    RiskLevel,
    SourceType,
    TAXONOMY_TREE,
    valid_subcategory,
)


class CapabilityRegistry:
    """统一能力注册中心。"""

    def __init__(self):
        self._capabilities: dict[str, CapabilityNode] = {}
        self._by_category: dict[str, list[str]] = {}
        self._by_source_type: dict[str, list[str]] = {}
        self._graph = None  # 延迟导入避免循环引用

    # ── 注册 ──────────────────────────────────────────────────────────────

    def register(self, node: CapabilityNode) -> str:
        """注册一个能力节点。已存在则更新。"""
        cid = node.capability_id
        self._capabilities[cid] = node
        self._by_category.setdefault(node.category, []).append(cid)
        self._by_source_type.setdefault(node.source_type, []).append(cid)
        return cid

    def register_from_dict(self, data: dict[str, Any]) -> str:
        """从字典创建并注册。"""
        node = CapabilityNode(**data)
        return self.register(node)

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get(self, capability_id: str) -> CapabilityNode | None:
        return self._capabilities.get(capability_id)

    def get_all(self) -> list[CapabilityNode]:
        return list(self._capabilities.values())

    def search(self, *, category: str | None = None,
               subcategory: str | None = None,
               source_type: str | None = None,
               maturity: str | None = None,
               risk_level: str | None = None,
               governance_approved: bool | None = None,
               keyword: str | None = None) -> list[CapabilityNode]:
        """多条件搜索能力。"""
        results = []
        for node in self._capabilities.values():
            if category and node.category != category:
                continue
            if subcategory and node.subcategory != subcategory:
                continue
            if source_type and node.source_type != source_type:
                continue
            if maturity and node.maturity != maturity:
                continue
            if risk_level and node.risk_level != risk_level:
                continue
            if governance_approved is not None and \
               node.governance_approved != governance_approved:
                continue
            if keyword:
                kw = keyword.lower()
                if kw not in node.name.lower() and \
                   kw not in node.description.lower() and \
                   kw not in node.category.lower():
                    continue
            results.append(node)
        return results

    # ── 分类查询 ──────────────────────────────────────────────────────────

    def get_by_category(self, category: str) -> list[CapabilityNode]:
        return [self._capabilities[cid] for cid in self._by_category.get(category, [])]

    def get_by_source_type(self, source_type: str) -> list[CapabilityNode]:
        return [self._capabilities[cid] for cid in self._by_source_type.get(source_type, [])]

    def get_high_risk_capabilities(self) -> list[CapabilityNode]:
        return [n for n in self._capabilities.values()
                if n.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)]

    def get_experimental_capabilities(self) -> list[CapabilityNode]:
        return [n for n in self._capabilities.values()
                if n.maturity == MaturityLevel.EXPERIMENTAL.value]

    def get_stable_capabilities(self) -> list[CapabilityNode]:
        return [n for n in self._capabilities.values()
                if n.maturity == MaturityLevel.STABLE.value]

    def get_quarantined_capabilities(self) -> list[CapabilityNode]:
        return [n for n in self._capabilities.values()
                if n.maturity == MaturityLevel.QUARANTINED.value]

    def get_orphan_capabilities(self) -> list[CapabilityNode]:
        """孤立能力：无依赖且无被依赖。"""
        all_deps: set[str] = set()
        all_dependents: set[str] = set()
        for node in self._capabilities.values():
            all_deps.update(node.dependencies)
            all_dependents.add(node.capability_id)
        return [n for n in self._capabilities.values()
                if n.capability_id not in all_deps
                and not n.dependencies
                and n.capability_id in all_dependents]

    def get_critical_dependencies(self) -> list[tuple[str, str]]:
        """高风险的依赖关系（依赖方与被依赖方均为高风险）。"""
        critical: list[tuple[str, str]] = []
        for node in self._capabilities.values():
            if node.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value):
                for dep_id in node.dependencies:
                    dep = self._capabilities.get(dep_id)
                    if dep and dep.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value):
                        critical.append((node.capability_id, dep_id))
        return critical

    # ── 更新 ──────────────────────────────────────────────────────────────

    def update_metrics(self, capability_id: str, *,
                       usage_count: int | None = None,
                       success_rate: float | None = None) -> bool:
        node = self._capabilities.get(capability_id)
        if not node:
            return False
        if usage_count is not None:
            node.usage_count = usage_count
        if success_rate is not None:
            node.success_rate = max(0.0, min(1.0, success_rate))
        return True

    def update_lifecycle(self, capability_id: str,
                         lifecycle_state: str) -> bool:
        node = self._capabilities.get(capability_id)
        if not node:
            return False
        node.lifecycle_state = lifecycle_state
        return True

    def update_maturity(self, capability_id: str, maturity: str) -> bool:
        node = self._capabilities.get(capability_id)
        if not node:
            return False
        if maturity in [m.value for m in MaturityLevel]:
            node.maturity = maturity
            return True
        return False

    def record_evolution(self, capability_id: str,
                         event: dict[str, Any]) -> bool:
        node = self._capabilities.get(capability_id)
        if not node:
            return False
        node.evolution_history.append(event)
        return True

    # ── 聚合查询 ──────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self._capabilities)

    @property
    def categories(self) -> list[str]:
        return sorted(self._by_category.keys())

    @property
    def source_types(self) -> list[str]:
        return sorted(self._by_source_type.keys())

    def get_summary(self) -> dict[str, Any]:
        by_cat: dict[str, int] = {}
        by_mat: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_src: dict[str, int] = {}
        for n in self._capabilities.values():
            by_cat[n.category] = by_cat.get(n.category, 0) + 1
            by_mat[n.maturity] = by_mat.get(n.maturity, 0) + 1
            by_risk[n.risk_level] = by_risk.get(n.risk_level, 0) + 1
            by_src[n.source_type] = by_src.get(n.source_type, 0) + 1
        return {
            "total": self.count,
            "by_category": by_cat,
            "by_maturity": by_mat,
            "by_risk_level": by_risk,
            "by_source_type": by_src,
            "categories": self.categories,
            "orphan_count": len(self.get_orphan_capabilities()),
            "high_risk_count": len(self.get_high_risk_capabilities()),
            "experimental_count": len(self.get_experimental_capabilities()),
            "stable_count": len(self.get_stable_capabilities()),
        }

    def export_json(self) -> str:
        import json
        nodes_data = []
        for n in self._capabilities.values():
            d = {
                "capability_id": n.capability_id,
                "name": n.name,
                "category": n.category,
                "subcategory": n.subcategory,
                "description": n.description,
                "maturity": n.maturity,
                "risk_level": n.risk_level,
                "source": n.source,
                "source_type": n.source_type,
                "dependencies": n.dependencies,
                "conflicts": n.conflicts,
                "related_patterns": n.related_patterns,
                "governance_approved": n.governance_approved,
                "lifecycle_state": n.lifecycle_state,
                "usage_count": n.usage_count,
                "success_rate": n.success_rate,
                "evolution_history": n.evolution_history,
                "metadata": n.metadata,
            }
            nodes_data.append(d)
        return json.dumps({
            "version": "1.0",
            "summary": self.get_summary(),
            "capabilities": nodes_data,
        }, ensure_ascii=False, indent=2)

    # ── Graph 集成 ────────────────────────────────────────────────────────

    def build_dependency_graph(self):
        """构建依赖图（延迟导入避免循环引用）。"""
        from capabilities.capability_graph import CapabilityGraph
        graph = CapabilityGraph()
        for node in self._capabilities.values():
            graph.add_node(node.capability_id, {
                "label": node.name,
                "category": node.category,
                "risk_level": node.risk_level,
            })
        for node in self._capabilities.values():
            for dep_id in node.dependencies:
                graph.add_dependency(node.capability_id, dep_id)
            for conflict_id in node.conflicts:
                graph.add_conflict(node.capability_id, conflict_id)
        self._graph = graph
        return graph

    @property
    def graph(self):
        return self._graph
