"""Pattern Extractor — Phase 2

将 OpenCode 的实现抽象为系统模式，不复制代码。

Output format:
    {
        "pattern_name": "...",
        "category": "planner|execution|context|memory|tool|runtime|governance",
        "problem_solved": "...",
        "mechanism": "...",
        "dvexa_compatibility": "compatible|adaptable|incompatible",
        "required_changes": [...],
        "risk_level": "low|medium|high|critical",
        "adoption_recommendation": "adopt|adapt|reject"
    }
"""

from __future__ import annotations

from typing import Any


class PatternExtractor:
    """从 OpenCode 分析结果中提取可复用的系统模式。

    关键原则:
        ❌ 不复制代码
        ❌ 不复制文件
        ❌ 不复制实现
        ✔ 提取设计模式
        ✔ 提取机制描述
        ✔ 提取架构思想
    """

    def __init__(self):
        self._patterns: list[dict] = []
        self._extracted_count = 0

    def extract(self, analysis_result: dict) -> dict:
        """从 analyzer 输出中提取所有模式。

        Args:
            analysis_result: OpenCodeAnalyzer.analyze_repo() 的返回值

        Returns:
            {
                "patterns": [...],
                "count": int,
                "summary": {...}
            }
        """
        self._patterns = []

        # 遍历所有模式类别
        categories = [
            "planner_patterns",
            "execution_patterns",
            "context_patterns",
            "memory_patterns",
            "tool_patterns",
            "runtime_patterns",
        ]

        for cat in categories:
            raw_patterns = analysis_result.get(cat, [])
            for rp in raw_patterns:
                extracted = self._extract_one(rp, cat.replace("_patterns", ""))
                if extracted:
                    self._patterns.append(extracted)

        # 从 risk_patterns 中提取风险模式
        for rp in analysis_result.get("risk_patterns", []):
            risk_pattern = self._extract_risk(rp)
            if risk_pattern:
                self._patterns.append(risk_pattern)

        self._extracted_count = len(self._patterns)

        return {
            "patterns": self._patterns,
            "count": self._extracted_count,
            "summary": self._build_summary(),
        }

    def _extract_one(self, raw: dict, category: str) -> dict | None:
        """从一条原始分析记录中提取模式。"""
        pattern_name = raw.get("pattern", "")
        if not pattern_name:
            return None

        # 映射到 DVexa 兼容性
        compatibility = self._assess_dvexa_compatibility(pattern_name, raw)
        risk = self._assess_risk(pattern_name, raw)
        recommendation = self._recommend(pattern_name, compatibility, risk)

        return {
            "pattern_name": pattern_name,
            "category": category,
            "source": raw.get("source", "unknown"),
            "problem_solved": raw.get("description", ""),
            "mechanism": raw.get("mechanism", ""),
            "dvexa_compatibility": compatibility,
            "required_changes": self._infer_required_changes(pattern_name, raw),
            "risk_level": risk,
            "adoption_recommendation": recommendation,
        }

    def _extract_risk(self, raw: dict) -> dict | None:
        """从 risk 记录中提取反向模式。"""
        risk_type = raw.get("type", "")
        return {
            "pattern_name": f"anti-pattern:{risk_type}",
            "category": "governance",
            "source": "risk_analysis",
            "problem_solved": raw.get("description", ""),
            "mechanism": f"Dvexa avoids this via: {raw.get('dvexa_equivalent', 'N/A')}",
            "dvexa_compatibility": "incompatible",
            "required_changes": ["NONE — this pattern should NOT be adopted"],
            "risk_level": raw.get("severity", "high"),
            "adoption_recommendation": "reject",
        }

    # ═══════════════════════════════════════════════════════════════════
    # Assessment Logic
    # ═══════════════════════════════════════════════════════════════════

    def _assess_dvexa_compatibility(self, name: str, raw: dict) -> str:
        """评估模式与 DVexa 的兼容性。"""
        incompatible_signals = [
            "effect-ts", "fiber", "monadic",
            "multi-agent", "spawn", "sub-agent",
            "bun", "zod",
        ]
        adaptable_signals = [
            "compaction", "retry", "schema",
            "state-machine", "lifecycle",
            "registry", "overflow",
            "truncation", "summary",
        ]
        compatible_signals = [
            "instruction", "message", "persistence",
            "event", "tool-interface",
        ]

        name_lower = name.lower()
        desc_lower = raw.get("description", "").lower()

        full = name_lower + " " + desc_lower

        for sig in incompatible_signals:
            if sig in full:
                return "incompatible"
        for sig in adaptable_signals:
            if sig in full:
                return "adaptable"

        return "compatible"

    def _assess_risk(self, name: str, raw: dict) -> str:
        risk_signals_high = ["autonomous", "uncontrolled", "unsafe",
                             "direct-write", "shell"]
        risk_signals_medium = ["replan", "complex", "coupling",
                               "concurrent", "spawn"]
        full = name.lower() + " " + raw.get("description", "").lower()

        for sig in risk_signals_high:
            if sig in full:
                return "high"
        for sig in risk_signals_medium:
            if sig in full:
                return "medium"
        return "low"

    def _recommend(self, name: str, compatibility: str, risk: str) -> str:
        if compatibility == "incompatible":
            return "reject"
        if risk == "high":
            return "adapt"
        if risk == "medium" and compatibility == "adaptable":
            return "adapt"
        return "adopt"

    def _infer_required_changes(self, name: str, raw: dict) -> list[str]:
        changes = []
        name_lower = name.lower()

        if "compaction" in name_lower:
            changes.append("Add compaction trigger to core/executor.py")
            changes.append("Add context pruning to memory/memory_store.py")
        if "retry" in name_lower:
            changes.append("Modify retry logic in core/executor.py")
            changes.append("Add backoff configuration to config/")
        if "registry" in name_lower:
            changes.append("Enhance capabilities/router.py with validation")
        if "state-machine" in name_lower or "lifecycle" in name_lower:
            changes.append("Enrich core/state.py TaskState enum")
            changes.append("Add transition guards to core/kernel.py")
        if "schema" in name_lower:
            changes.append("Add validation layer to tools/ base classes")
        if "instruction" in name_lower:
            changes.append("Enhance agents/base_agent.py instruction composition")
            changes.append("Add instruction layering to config/")
        if "message" in name_lower:
            changes.append("Add structured message types to memory/")
        if "event" in name_lower:
            changes.append("Add event bus to evaluation/ layer only")

        return changes if changes else ["No code changes required — pattern for reference only"]

    def _build_summary(self) -> dict:
        by_category: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_recommendation: dict[str, int] = {}

        for p in self._patterns:
            cat = p.get("category", "unknown")
            risk = p.get("risk_level", "unknown")
            rec = p.get("adoption_recommendation", "unknown")

            by_category[cat] = by_category.get(cat, 0) + 1
            by_risk[risk] = by_risk.get(risk, 0) + 1
            by_recommendation[rec] = by_recommendation.get(rec, 0) + 1

        return {
            "total_patterns": len(self._patterns),
            "by_category": by_category,
            "by_risk": by_risk,
            "by_recommendation": by_recommendation,
            "adoptable_count": by_recommendation.get("adopt", 0),
            "adaptable_count": by_recommendation.get("adapt", 0),
            "rejected_count": by_recommendation.get("reject", 0),
        }

    # ═══════════════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════════════

    def get_patterns(self) -> list[dict]:
        return list(self._patterns)

    def get_by_category(self, category: str) -> list[dict]:
        return [p for p in self._patterns if p.get("category") == category]

    def get_adoptable(self) -> list[dict]:
        return [p for p in self._patterns
                if p.get("adoption_recommendation") in ("adopt", "adapt")]

    def get_rejected(self) -> list[dict]:
        return [p for p in self._patterns
                if p.get("adoption_recommendation") == "reject"]
