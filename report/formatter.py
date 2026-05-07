"""Report Formatter — 执行报告格式化输出（v1.88）

同时生成：
  1. text 控制台报告
  2. JSON 报告
"""

from __future__ import annotations

import json
from typing import Any

from report.execution_report import ExecutionReport


class ReportFormatter:
    """报告格式化器。"""

    SEPARATOR = "━" * 50

    def to_text(self, report: ExecutionReport) -> str:
        """生成控制台格式报告。"""
        d = report.to_dict()
        lines = [
            self.SEPARATOR,
            "DVexa Execution Report",
            self.SEPARATOR,
            "",
            f"Task: {d.get('task_input', 'N/A')[:80]}",
            f"Status: {'✓ 成功' if d.get('success') else '✗ 失败'}",
            f"Health: {d.get('system_health', 'N/A')}",
            "",
            "--- Execution ---",
        ]

        steps = d.get("steps", [])
        if steps:
            lines.append(f"  {len(steps)} step(s) executed")
            for i, step in enumerate(steps, 1):
                action = step.get("action", "") or ""
                tool = step.get("tool", "") or ""
                lines.append(f"  {i}. {action} → [{tool}]")
        else:
            lines.append("  (no steps)")

        skills = d.get("skills_used", [])
        if skills:
            lines.append("")
            lines.append("--- Skills ---")
            for s in skills:
                lines.append(f"  • {s}")

        path = d.get("routing_path", [])
        if path:
            lines.append("")
            lines.append("--- Routing Path ---")
            lines.append(f"  {' → '.join(path)}")

        governance = d.get("governance_changes", [])
        if governance:
            lines.append("")
            lines.append("--- Governance ---")
            for g in governance:
                lines.append(f"  • {g}")

        errors = d.get("errors", [])
        if errors:
            lines.append("")
            lines.append("--- Errors ---")
            for e in errors:
                lines.append(f"  ✗ {e}")
        else:
            lines.append("")
            lines.append("Errors: none")

        flags = d.get("risk_flags", [])
        if flags:
            lines.append("")
            lines.append("--- Risk Flags ---")
            for f in flags:
                lines.append(f"  ⚠ {f}")

        lines.append("")
        lines.append("--- Metrics ---")
        lines.append(f"  Token usage: {d.get('token_usage', 0)}")
        lines.append(f"  Latency: {d.get('latency', {})}")
        lines.append(f"  System health: {d.get('system_health', 'N/A')}")

        ext = d.get("external_calls", [])
        if ext:
            lines.append("")
            lines.append("--- External Calls ---")
            for e in ext:
                lines.append(f"  • {e}")

        if d.get("insight_summary"):
            lines.append("")
            lines.append(f"Insight: {d['insight_summary']}")

        lines.append("")
        lines.append(self.SEPARATOR)
        return "\n".join(lines)

    def to_summary(self, report: ExecutionReport) -> str:
        """生成一行摘要。"""
        d = report.to_dict()
        status = "✓" if d.get("success") else "✗"
        return (
            f"[{status}] {d.get('task_input', 'N/A')[:50]} | "
            f"{d.get('system_health', 'N/A')} | "
            f"{len(d.get('steps', []))} steps | "
            f"{d.get('token_usage', 0)} tokens"
        )

    def to_json(self, report: ExecutionReport, indent: int = 2) -> str:
        """生成 JSON 格式报告。"""
        return json.dumps(report.to_dict(), ensure_ascii=False, indent=indent)
