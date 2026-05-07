"""Insight Agent — 系统洞察入口

编排 analyzer → drift detector → report generator 全流程。
不参与任何执行或决策。
"""

from __future__ import annotations
from insight.analyzer import SystemAnalyzer
from insight.drift import DriftDetector
from insight.report import ReportGenerator


class InsightAgent:
    """系统洞察代理 — 只观察，不参与，不影响。

    使用方式:
        agent = InsightAgent(governor=skill_governor, memory=memory_store)
        report = agent.generate_report()
        print(agent.report_to_text(report))
    """

    def __init__(self, governor=None, memory=None):
        self._analyzer = SystemAnalyzer(governor, memory)
        self._drift = DriftDetector()
        self._report_gen = ReportGenerator()

    def generate_report(self) -> dict:
        """生成完整系统洞察报告。"""
        analysis = self._analyzer.analyze()
        drift = self._drift.detect(analysis)
        return self._report_gen.generate(analysis, drift)

    def report_to_text(self, report: dict) -> str:
        """将报告转为可读文本。"""
        return self._report_gen.to_text(report)

    def quick_health(self) -> str:
        """快速健康检查，返回健康状态字符串。"""
        report = self.generate_report()
        return report["health_status"]
