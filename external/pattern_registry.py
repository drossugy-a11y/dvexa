"""Pattern Registry — Phase 6

管理模式版本、采纳状态、风险级别。对接 TBRZ 规范。
"""

from __future__ import annotations

from typing import Any


class PatternRegistry:
    """模式注册表 — 对接 TBRZ 吞并知识库规范。

    每个 pattern 追踪:
      - 版本
      - 采纳状态
      - 风险级别
      - 源仓库
      - TBRZ 阶段
    """

    # TBRZ Phase 0-7 映射
    _TBRZ_STAGES = {
        "extracted": 1,
        "reviewed": 2,
        "sandboxed": 3,
        "regression_passed": 4,
        "governance_approved": 5,
        "registered": 6,
        "adopted": 7,
    }

    def __init__(self):
        self._registry: dict[str, dict] = {}
        self._adoption_log: list[dict] = []

    def register(self, pattern: dict, review: dict | None = None,
                 source_repo: str = "sst/opencode") -> str:
        """注册一个模式。

        Args:
            pattern: PatternExtractor 输出的 pattern dict
            review: AssimilationReview 输出的 review dict（可选）
            source_repo: 来源仓库

        Returns:
            pattern_id
        """
        name = pattern.get("pattern_name", "")
        category = pattern.get("category", "")
        pid = f"{category}/{name}"

        entry = {
            "pattern_id": pid,
            "pattern_name": name,
            "category": category,
            "source_repo": source_repo,
            "version": 1,
            "adoption_status": "extracted",
            "tbrz_stage": self._TBRZ_STAGES["extracted"],
            "risk_level": pattern.get("risk_level", "unknown"),
            "dvexa_compatibility": pattern.get("dvexa_compatibility", "unknown"),
            "adoption_recommendation": pattern.get("adoption_recommendation", "unknown"),
            "mechanism": pattern.get("mechanism", ""),
            "problem_solved": pattern.get("problem_solved", ""),
            "required_changes": pattern.get("required_changes", []),
            "review": review,
            "adoption_date": None,
            "adoption_notes": "",
        }

        if pid in self._registry:
            entry["version"] = self._registry[pid]["version"] + 1

        self._registry[pid] = entry
        self._adoption_log.append({
            "action": "register",
            "pattern_id": pid,
            "source_repo": source_repo,
        })

        return pid

    def register_batch(self, patterns: list[dict],
                       reviews: dict[str, dict] | None = None,
                       source_repo: str = "sst/opencode") -> list[str]:
        """批量注册模式。"""
        ids = []
        reviews = reviews or {}
        for p in patterns:
            rv = reviews.get(p.get("pattern_name", ""))
            pid = self.register(p, review=rv, source_repo=source_repo)
            ids.append(pid)
        return ids

    def adopt(self, pattern_id: str) -> bool:
        """标记一个模式为已采纳（Phase 7 到达）。"""
        if pattern_id in self._registry:
            self._registry[pattern_id]["adoption_status"] = "adopted"
            self._registry[pattern_id]["tbrz_stage"] = self._TBRZ_STAGES["adopted"]
            from datetime import datetime, timezone
            self._registry[pattern_id]["adoption_date"] = \
                datetime.now(timezone.utc).isoformat()
            self._adoption_log.append({
                "action": "adopt",
                "pattern_id": pattern_id,
            })
            return True
        return False

    def advance_stage(self, pattern_id: str, stage: str) -> bool:
        """将模式推进到下一个 TBRZ 阶段。"""
        if pattern_id not in self._registry:
            return False
        if stage in self._TBRZ_STAGES:
            self._registry[pattern_id]["adoption_status"] = stage
            self._registry[pattern_id]["tbrz_stage"] = self._TBRZ_STAGES[stage]
            return True
        return False

    def get_pattern(self, pattern_id: str) -> dict | None:
        return self._registry.get(pattern_id)

    def get_patterns(self) -> list[dict]:
        return list(self._registry.values())

    def search(self, category: str | None = None,
               status: str | None = None,
               risk_level: str | None = None,
               recommendation: str | None = None) -> list[dict]:
        """按条件搜索模式。"""
        results = []
        for entry in self._registry.values():
            if category and entry["category"] != category:
                continue
            if status and entry["adoption_status"] != status:
                continue
            if risk_level and entry["risk_level"] != risk_level:
                continue
            if recommendation and \
               entry["adoption_recommendation"] != recommendation:
                continue
            results.append(entry)
        return results

    def get_adopted_patterns(self) -> list[dict]:
        return [e for e in self._registry.values()
                if e["adoption_status"] == "adopted"]

    def get_by_category(self, category: str) -> list[dict]:
        return [e for e in self._registry.values()
                if e["category"] == category]

    def get_count(self) -> int:
        return len(self._registry)

    def get_adoption_log(self) -> list[dict]:
        return list(self._adoption_log)

    def get_summary(self) -> dict:
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        adopted_count = 0

        for e in self._registry.values():
            c = e["category"]
            s = e["adoption_status"]
            r = e["risk_level"]
            by_category[c] = by_category.get(c, 0) + 1
            by_status[s] = by_status.get(s, 0) + 1
            by_risk[r] = by_risk.get(r, 0) + 1
            if s == "adopted":
                adopted_count += 1

        return {
            "total_registered": len(self._registry),
            "total_adopted": adopted_count,
            "by_category": by_category,
            "by_status": by_status,
            "by_risk": by_risk,
        }

    def export_json(self) -> str:
        """导出为 JSON。"""
        import json
        return json.dumps({
            "patterns": list(self._registry.values()),
            "log": self._adoption_log,
            "summary": self.get_summary(),
        }, ensure_ascii=False, indent=2)

    # ─── Capability Taxonomy 映射 ─────────────────────────────────────────

    # OpenCode pattern category → DVexa taxonomy (category, subcategory)
    _CATEGORY_MAP: dict[str, tuple[str, str]] = {
        "planner": ("planning", "decomposition"),
        "execution": ("execution", "tool-routing"),
        "context": ("memory", "context-compression"),
        "memory": ("memory", "persistent-state"),
        "tool": ("execution", "tool-routing"),
        "runtime": ("runtime", ""),
    }

    def to_capability_node(self, pattern_id: str) -> dict | None:
        """将已采纳的 pattern 映射为 CapabilityNode 数据。

        只映射已 adopted 的 pattern。
        自动推断 category/subcategory。
        """
        pattern = self._registry.get(pattern_id)
        if not pattern:
            return None
        if pattern.get("adoption_status") != "adopted":
            return None

        category = pattern.get("category", "external")
        cat_info = self._CATEGORY_MAP.get(category, ("external", ""))
        taxonomy_cat, taxonomy_sub = cat_info
        if not taxonomy_sub:
            taxonomy_sub = category

        return {
            "capability_id": f"taxonomy:assimilation:{pattern_id}",
            "name": pattern.get("pattern_name", pattern_id),
            "category": taxonomy_cat,
            "subcategory": taxonomy_sub,
            "description": pattern.get("problem_solved", ""),
            "maturity": "experimental",
            "risk_level": pattern.get("risk_level", "low"),
            "source": pattern.get("source_repo", "sst/opencode"),
            "source_type": "assimilation",
            "dependencies": [],
            "conflicts": [],
            "related_patterns": [],
            "governance_approved": True,
            "lifecycle_state": "active",
            "usage_count": 0,
            "success_rate": 1.0,
            "evolution_history": [],
            "metadata": {
                "pattern_id": pattern_id,
                "tbrz_stage": pattern.get("tbrz_stage", 0),
                "mechanism": pattern.get("mechanism", ""),
            },
        }

    def get_adopted_capability_nodes(self) -> list[dict]:
        """获取所有 adopted pattern 对应的 CapabilityNode 数据。"""
        nodes = []
        for pid in self._registry:
            node = self.to_capability_node(pid)
            if node:
                nodes.append(node)
        return nodes
