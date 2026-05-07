"""External Call & Assimilation Reports — 外部调用与同化报告（v1.88）

标准数据结构：
  - ExternalCallReport: 每次 sandbox 调用的记录
  - AssimilationReport: 外部项目能力分析报告（v1.88 新增标准结构）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExternalCallReport:
    """单次外部 agent 调用报告。"""
    adapter_name: str
    input_summary: str
    output_summary: str
    latency_sec: float
    output_size: int
    truncated: bool = False
    timeout: bool = False
    error: str | None = None
    sandbox_version: str = "1.0"


@dataclass
class AssimilationReport:
    """外部能力同化分析报告。

    用于分析外部项目并提取能力模式。
    绝不包含任何自动注册或修改系统的操作。
    """
    source_project: str
    detected_capabilities: list[dict] = field(default_factory=list)
    reusable_patterns: list[str] = field(default_factory=list)
    candidate_skills: list[dict] = field(default_factory=list)
    dependency_risks: list[str] = field(default_factory=list)
    integration_complexity: str = "unknown"       # low / medium / high
    suggested_actions: list[str] = field(default_factory=list)
    forbidden_operations: list[str] = field(default_factory=list)


class ExternalReporter:
    """外部 agent 调用记录器。

    纯记录，不参与任何决策。
    append-only 日志。
    """

    def __init__(self):
        self._reports: list[ExternalCallReport] = []

    def record(self, report: ExternalCallReport):
        """追加一条调用记录。"""
        self._reports.append(report)

    def summary(self) -> dict:
        """聚合统计摘要。"""
        if not self._reports:
            return {
                "total_calls": 0,
                "error_rate": 0.0,
                "avg_latency": 0.0,
                "timeout_rate": 0.0,
            }

        n = len(self._reports)
        errors = sum(1 for r in self._reports if r.error)
        timeouts = sum(1 for r in self._reports if r.timeout)
        total_latency = sum(r.latency_sec for r in self._reports)

        return {
            "total_calls": n,
            "error_rate": round(errors / n, 3),
            "avg_latency": round(total_latency / n, 3),
            "timeout_rate": round(timeouts / n, 3),
        }

    def list_recent(self, n: int = 10) -> list[ExternalCallReport]:
        """返回最近 n 条记录。"""
        return self._reports[-n:]
