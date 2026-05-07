"""Report Generator — 系统洞察报告生成（v1.87）

新增生态稳定性、能力流失、恢复成功率指标。
"""

from __future__ import annotations


class ReportGenerator:
    """报告生成器 — 将分析数据转化为系统报告。"""

    HEALTH_MAP = {
        "healthy": "系统运行正常，无异常信号",
        "degraded": "部分指标异常，建议关注",
        "unstable": "多项指标偏离基线，建议排查",
    }

    def generate(self, analysis: dict, drift: dict) -> dict:
        """生成完整系统洞察报告。"""
        health = self._assess_health(analysis, drift)
        insights = self._extract_insights(analysis, drift)
        recommendations = self._generate_recommendations(analysis, drift)

        return {
            "summary": self._build_summary(analysis, drift, health),
            "health_status": health,
            "health_label": self.HEALTH_MAP.get(health, "unknown"),
            "key_insights": insights,
            "recommendations": recommendations,
            "drift": drift,
            "analysis": analysis,
        }

    def to_text(self, report: dict) -> str:
        lines = [
            "=" * 48,
            "DVexa 系统洞察报告",
            "=" * 48,
            f"健康状态: {report['health_status']} — {report['health_label']}",
            "",
            "--- 生态指标 ---",
        ]
        analysis = report.get("analysis", {})
        lines.append(f"  生态稳定性: {analysis.get('ecosystem_stability_score', 'N/A')}")
        lines.append(f"  能力流失率: {analysis.get('capability_churn_rate', 'N/A')}")
        lines.append(f"  隔离中 skill: {analysis.get('quarantine_count', 0)}")
        lines.append(f"  恢复成功率: {analysis.get('recovery_success_rate', 'N/A')}")
        lines.append("")
        lines.append("--- 关键洞察 ---")
        for item in report.get("key_insights", []):
            lines.append(f"  • {item}")
        lines.append("")
        lines.append("--- 建议 ---")
        for item in report.get("recommendations", []):
            lines.append(f"  • {item}")

        if report.get("drift", {}).get("drift_detected"):
            lines.append("")
            lines.append("⚠ 漂移警告:")
            for comp in report["drift"]["affected_components"]:
                lines.append(f"  • {comp}")

        lines.append("")
        lines.append(f"摘要: {report.get('summary', '')}")
        return "\n".join(lines)

    def _assess_health(self, analysis: dict, drift: dict) -> str:
        declining = analysis.get("declining_skills", [])
        conflicts = analysis.get("conflicts", [])
        drift_detected = drift.get("drift_detected", False)
        drift_score = drift.get("drift_score", 0.0)
        quarantine = analysis.get("quarantine_count", 0)
        stability = analysis.get("ecosystem_stability_score", 1.0)

        if drift_detected or len(declining) > 2 or quarantine > 1 or stability < 0.5:
            return "unstable"
        if len(declining) > 0 or len(conflicts) > 0 or drift_score > 0.1 or quarantine > 0:
            return "degraded"
        return "healthy"

    def _extract_insights(self, analysis: dict, drift: dict) -> list[str]:
        insights = []
        hot = analysis.get("hot_skills", [])
        declining = analysis.get("declining_skills", [])
        conflicts = analysis.get("conflicts", [])
        quarantine = analysis.get("quarantine_count", 0)
        stability = analysis.get("ecosystem_stability_score", 1.0)

        if hot:
            names = ", ".join(s["name"] for s in hot[:3])
            insights.append(f"高活跃 skill: {names}")
        if declining:
            names = ", ".join(s["name"] for s in declining)
            insights.append(f"需关注 skill: {names}")
        if conflicts:
            insights.append(f"检测到 {len(conflicts)} 组 skill 功能重叠")
        if quarantine > 0:
            insights.append(f"{quarantine} 个 skill 处于隔离状态")
        if drift.get("drift_detected"):
            insights.append("系统行为模式发生漂移")
        if stability < 0.8:
            insights.append(f"生态稳定性评分偏低: {stability}")
        if analysis.get("execution_count", 0) == 0:
            insights.append("系统尚无执行记录")

        return insights

    def _generate_recommendations(self, analysis: dict, drift: dict) -> list[str]:
        recs = []
        declining = analysis.get("declining_skills", [])
        conflicts = analysis.get("conflicts", [])
        quarantine = analysis.get("quarantine_count", 0)

        if declining:
            names = ", ".join(s["name"] for s in declining)
            recs.append(f"审查 {names} 的失败原因")
        if quarantine > 0:
            recs.append(f"{quarantine} 个 skill 被隔离，可手动触发 try_recovery()")
        if conflicts:
            for c in conflicts:
                recs.append(
                    f"合并或明确分工: {c['skill_a']} ↔ {c['skill_b']} "
                    f"(相似度 {c['similarity']})"
                )
        if drift.get("drift_detected"):
            recs.append("检查近期变更是否引入预期外行为偏移")

        if not recs:
            recs.append("系统状态稳定，无需干预")
        return recs

    def _build_summary(self, analysis: dict, drift: dict, health: str) -> str:
        n_skills = len(analysis.get("skill_summary", []))
        n_declining = len(analysis.get("declining_skills", []))
        n_conflicts = len(analysis.get("conflicts", []))
        exec_count = analysis.get("execution_count", 0)
        drift_score = drift.get("drift_score", 0.0)
        stability = analysis.get("ecosystem_stability_score", 1.0)
        quarantine = analysis.get("quarantine_count", 0)
        return (
            f"系统管理 {n_skills} 个 skill, 已执行 {exec_count} 次, "
            f"{n_declining} 个需关注, {quarantine} 个隔离, "
            f"{n_conflicts} 组冲突, 生态稳定性 {stability:.2f}, "
            f"漂移评分 {drift_score:.2f}, 整体 {health}"
        )
