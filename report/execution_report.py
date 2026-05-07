"""Execution Report — 执行报告标准结构（v1.88）

每次任务执行结束后自动生成完整系统行为报告。
纯观察层：只 collect() / format() / export()，不修改任何系统状态。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from report.metrics import MetricsCollector


@dataclass
class ExecutionReport:
    """统一执行报告结构。"""
    task_id: str = ""
    task_input: str = ""
    success: bool = True
    summary: str = ""
    steps: list[dict] = field(default_factory=list)
    skills_used: list[str] = field(default_factory=list)
    routing_path: list[str] = field(default_factory=list)
    governance_changes: list[dict] = field(default_factory=list)
    token_usage: int = 0
    latency: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    system_health: str = "healthy"
    risk_flags: list[str] = field(default_factory=list)
    insight_summary: str = ""
    external_calls: list[dict] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        """序列化为 dict。"""
        return asdict(self)

    def to_json(self) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ExecutionReportBuilder:
    """执行报告构建器。

    从 kernel 执行结果 + metrics + governance + insight 构建完整报告。
    """

    def __init__(self):
        self._metrics = MetricsCollector()

    def from_kernel_result(
        self,
        result: dict | None = None,
        governor=None,
        insight_report: dict | None = None,
        external_reporter=None,
    ) -> ExecutionReport:
        """从 kernel 执行结果构建报告。"""
        report = ExecutionReport()
        report.timestamp = datetime.now().isoformat()

        if not result:
            report.summary = "无执行数据"
            return report

        report.task_id = result.get("task_id", "")
        report.task_input = result.get("goal", "")
        report.success = result.get("status", "") in ("completed", "success")
        report.summary = self._build_summary(result)

        # 步骤记录
        steps = result.get("steps", []) or []
        report.steps = steps

        # 错误提取
        for step in steps:
            output = str(step.get("tool_output", ""))
            if output.startswith("[工具错误]") or output.startswith("[工具不可用]"):
                report.errors.append(f"步骤{step.get('step_id','?')}: {output}")

        # metrics 收集
        metrics = self._metrics.collect(
            kernel_result=result,
            governor=governor,
            insight_report=insight_report,
        )
        report.skills_used = metrics.get("skills_used", [])
        report.routing_path = metrics.get("routing_path", [])
        report.governance_changes = metrics.get("governance_changes", [])
        report.token_usage = metrics.get("token_usage", 0)
        report.risk_flags = metrics.get("risk_flags", [])

        # health
        if insight_report:
            report.system_health = insight_report.get("health_status", "healthy")
            report.insight_summary = insight_report.get("summary", "")

        # external calls
        if external_reporter:
            ext_summary = external_reporter.summary()
            if ext_summary.get("total_calls", 0) > 0:
                report.external_calls.append(ext_summary)

        return report

    def _build_summary(self, result: dict) -> str:
        goal = result.get("goal", "")
        status = result.get("status", "")
        steps = result.get("steps", []) or []
        return f"任务: {goal[:60]} | 状态: {status} | 步骤: {len(steps)}"
