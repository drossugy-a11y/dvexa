"""Metrics Collector — 执行指标收集（v1.88）

从 post-execution 数据中提取指标。
纯读取，不修改任何系统状态。
"""

from __future__ import annotations
from typing import Any


class MetricsCollector:
    """指标收集器 — 从执行结果中提取结构化指标。

    纯观察层：只 collect()，不修改 governance/router/skill score/lifecycle。
    """

    def collect(
        self,
        kernel_result: dict | None = None,
        governor=None,
        insight_report: dict | None = None,
    ) -> dict:
        """从执行后数据收集指标。

        Args:
            kernel_result: kernel.run_task() 的返回值
            governor: SkillGovernor 实例（可选）
            insight_report: InsightAgent 的报告（可选）

        Returns:
            dict: {
                "skills_used": [str],
                "routing_path": [str],
                "governance_changes": [dict],
                "token_usage": int,
                "latency": dict,
                "errors": [str],
                "risk_flags": [str],
            }
        """
        metrics: dict[str, Any] = {
            "skills_used": [],
            "routing_path": [],
            "governance_changes": [],
            "token_usage": 0,
            "latency": {},
            "errors": [],
            "risk_flags": [],
        }

        if not kernel_result:
            return metrics

        self._collect_steps(kernel_result, metrics)
        self._collect_governance(kernel_result, governor, metrics)
        self._collect_insight(insight_report, metrics)
        self._compute_risk_flags(metrics)

        return metrics

    def _collect_steps(self, result: dict, metrics: dict):
        steps = result.get("steps", []) or []
        skills = set()
        path = []

        for step in steps:
            tool = step.get("tool", "")
            if tool:
                skills.add(tool)
                path.append(tool)

        metrics["skills_used"] = sorted(skills)
        metrics["routing_path"] = path
        metrics["token_usage"] = self._estimate_tokens(result, steps)

    def _collect_governance(self, result: dict, governor, metrics: dict):
        changes = result.get("governance_changes", [])
        if changes:
            metrics["governance_changes"] = changes

    def _collect_insight(self, insight_report: dict | None, metrics: dict):
        if not insight_report:
            return
        drift = insight_report.get("drift", {})
        if drift.get("drift_detected"):
            metrics["risk_flags"].append("drift_detected")

        health = insight_report.get("health_status", "")
        if health == "unstable":
            metrics["risk_flags"].append("system_unstable")
        elif health == "degraded":
            metrics["risk_flags"].append("system_degraded")

    def _compute_risk_flags(self, metrics: dict):
        errors = metrics.get("errors", [])
        if len(errors) > 2:
            metrics["risk_flags"].append("high_error_rate")

    def _estimate_tokens(self, result: dict, steps: list[dict]) -> int:
        """估算 token 消耗（基于输入输出长度）。"""
        total = 0
        task_input = result.get("goal", "") or ""
        total += len(task_input) // 2

        for step in steps:
            tool_input = step.get("tool_input", "") or ""
            tool_output = step.get("tool_output", "") or ""
            total += len(tool_input) // 2
            total += len(tool_output) // 2

        return total
