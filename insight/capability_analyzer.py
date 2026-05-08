"""Capability Analyzer v1.0 — 系统能力分析器

纯观察层。不修改系统状态，不参与执行决策。
分析 CapabilityRegistry 中的能力分布，发现热点/风险/孤立节点。
"""

from __future__ import annotations

from typing import Any


class CapabilityAnalyzer:
    """系统能力分析器 — 只读观察维度。"""

    def __init__(self, registry=None, governor=None):
        self._registry = registry
        self._governor = governor

    def analyze_system_capabilities(self) -> dict[str, Any]:
        """分析整个系统的能力状态。

        Returns:
            {
                "total_capabilities": int,
                "stable_capabilities": int,
                "experimental_capabilities": int,
                "high_risk_capabilities": int,
                "orphan_capabilities": [...],
                "critical_dependencies": [...],
                "governance_hotspots": [...],
                "most_used_capabilities": [...],
                "least_reliable_capabilities": [...],
                "category_distribution": {...},
                "maturity_distribution": {...},
            }
        """
        if self._registry is None:
            return self._empty_report()

        nodes = self._registry.get_all()
        if not nodes:
            return self._empty_report()

        # 基础统计
        total = len(nodes)
        stable = [n for n in nodes if n.maturity == "stable"]
        experimental = [n for n in nodes if n.maturity == "experimental"]
        high_risk = [n for n in nodes if n.risk_level in ("high", "critical")]
        quarantined = [n for n in nodes if n.maturity == "quarantined"]

        # 孤立能力
        orphans = self._registry.get_orphan_capabilities()

        # 关键依赖
        critical_deps = self._registry.get_critical_dependencies()

        # 治理热点（高风险 + 实验性 + 隔离的并集）
        hotspot_ids = set()
        for n in high_risk + experimental + quarantined:
            hotspot_ids.add(n.capability_id)
        governance_hotspots = [
            {
                "capability_id": cid,
                "name": self._registry.get(cid).name if self._registry.get(cid) else "",
                "maturity": self._registry.get(cid).maturity if self._registry.get(cid) else "",
                "risk_level": self._registry.get(cid).risk_level if self._registry.get(cid) else "",
            }
            for cid in sorted(hotspot_ids)
        ]

        # 最多使用
        most_used = sorted(nodes, key=lambda n: n.usage_count, reverse=True)[:10]
        most_used_list = [
            {"capability_id": n.capability_id, "name": n.name, "usage_count": n.usage_count}
            for n in most_used if n.usage_count > 0
        ]

        # 最不可靠
        least_reliable = sorted(nodes, key=lambda n: n.success_rate)[:10]
        least_reliable_list = [
            {"capability_id": n.capability_id, "name": n.name, "success_rate": n.success_rate}
            for n in least_reliable if n.usage_count > 0
        ]

        # 分布统计
        category_dist: dict[str, int] = {}
        maturity_dist: dict[str, int] = {}
        risk_dist: dict[str, int] = {}
        for n in nodes:
            category_dist[n.category] = category_dist.get(n.category, 0) + 1
            maturity_dist[n.maturity] = maturity_dist.get(n.maturity, 0) + 1
            risk_dist[n.risk_level] = risk_dist.get(n.risk_level, 0) + 1

        # 演化活动度
        evolution_active = sum(1 for n in nodes if len(n.evolution_history) > 0)

        return {
            "total_capabilities": total,
            "stable_capabilities": len(stable),
            "experimental_capabilities": len(experimental),
            "high_risk_capabilities": len(high_risk),
            "quarantined_capabilities": len(quarantined),
            "orphan_capabilities": [
                {"capability_id": n.capability_id, "name": n.name, "category": n.category}
                for n in orphans
            ],
            "critical_dependencies": [
                {"dependent": d[0], "depends_on": d[1]} for d in critical_deps
            ],
            "governance_hotspots": governance_hotspots,
            "most_used_capabilities": most_used_list,
            "least_reliable_capabilities": least_reliable_list,
            "category_distribution": category_dist,
            "maturity_distribution": maturity_dist,
            "risk_distribution": risk_dist,
            "evolution_active_count": evolution_active,
        }

    @staticmethod
    def _empty_report() -> dict[str, Any]:
        return {
            "total_capabilities": 0,
            "stable_capabilities": 0,
            "experimental_capabilities": 0,
            "high_risk_capabilities": 0,
            "quarantined_capabilities": 0,
            "orphan_capabilities": [],
            "critical_dependencies": [],
            "governance_hotspots": [],
            "most_used_capabilities": [],
            "least_reliable_capabilities": [],
            "category_distribution": {},
            "maturity_distribution": {},
            "risk_distribution": {},
            "evolution_active_count": 0,
        }
