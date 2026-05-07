"""System Analyzer — 系统行为分析（v1.87）

从 governance + memory 读取数据，分析 skill 使用趋势、错误模式、生态稳定性。"""

from __future__ import annotations


class SystemAnalyzer:
    """系统分析器 — 分析 skill 健康度、使用频率、错误模式。"""

    def __init__(self, governor=None, memory=None):
        self._governor = governor
        self._memory = memory

    def analyze(self) -> dict:
        """执行全部分析，返回结构化分析结果。"""
        skills_data = self._governor.list_all() if self._governor else []
        conflicts = self._governor.detect_conflicts() if self._governor else []
        exec_history = self._memory.get_all() if self._memory else []

        return {
            "hot_skills": self._find_hot_skills(skills_data),
            "declining_skills": self._find_declining_skills(skills_data),
            "error_clusters": self._cluster_errors(skills_data),
            "conflicts": [
                {"skill_a": c.skill_a, "skill_b": c.skill_b,
                 "similarity": c.similarity, "overlap": c.overlap_keywords}
                for c in conflicts
            ],
            "skill_summary": skills_data,
            "execution_count": len(exec_history),
            "ecosystem_stability_score": self._ecosystem_stability(),
            "capability_churn_rate": self._capability_churn(),
            "quarantine_count": self._quarantine_count(),
            "recovery_success_rate": self._recovery_success_rate(),
        }

    def _ecosystem_stability(self) -> float:
        if not self._governor:
            return 1.0
        return self._governor.ecosystem_stability_score()

    def _capability_churn(self) -> float:
        if not self._governor:
            return 0.0
        return self._governor.capability_churn_rate()

    def _quarantine_count(self) -> int:
        if not self._governor:
            return 0
        return self._governor.quarantine_count()

    def _recovery_success_rate(self) -> float:
        if not self._governor:
            return 1.0
        return self._governor.recovery_success_rate()

    def _find_hot_skills(self, skills: list[dict]) -> list[dict]:
        used = [s for s in skills if s["usage"] > 0]
        used.sort(key=lambda s: s["combined_score"], reverse=True)
        return used[:5]

    def _find_declining_skills(self, skills: list[dict]) -> list[dict]:
        return [
            s for s in skills
            if s["status"] in ("degraded", "quarantined", "removed")
            or s.get("consecutive_failures", 0) >= 3
        ]

    def _cluster_errors(self, skills: list[dict]) -> list[dict]:
        clusters: dict[str, list[str]] = {}
        for s in skills:
            clusters.setdefault(s["status"], []).append(s["name"])
        return [
            {"status": status, "skills": names, "count": len(names)}
            for status, names in sorted(clusters.items())
        ]
