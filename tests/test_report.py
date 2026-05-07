"""Tests for Execution Report Layer (v1.88)"""

import json
import pytest

from report.metrics import MetricsCollector
from report.execution_report import ExecutionReport, ExecutionReportBuilder
from report.formatter import ReportFormatter


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_kernel_result(**overrides):
    base = {
        "task_id": "task-1",
        "goal": "分析数据",
        "status": "completed",
        "steps": [
            {
                "step_id": 1,
                "action": "execute python",
                "tool": "code",
                "tool_input": "1+1",
                "tool_output": "2",
            },
            {
                "step_id": 2,
                "action": "call llm",
                "tool": "llm",
                "tool_input": "分析结果",
                "tool_output": "分析完成",
            },
        ],
        "result": "ok",
        "retry_count": 0,
    }
    base.update(overrides)
    return base


def _make_minimal_result():
    return {"task_id": "t1", "goal": "", "status": "completed", "steps": [], "result": ""}


# ─── MetricsCollector ─────────────────────────────────────────────────────────

class TestMetricsCollector:
    def test_collect_from_complete_result(self):
        mc = MetricsCollector()
        result = mc.collect(kernel_result=_make_kernel_result())
        assert result["skills_used"] == ["code", "llm"]
        assert result["routing_path"] == ["code", "llm"]
        assert result["token_usage"] > 0

    def test_collect_from_minimal_result(self):
        mc = MetricsCollector()
        result = mc.collect(kernel_result=_make_minimal_result())
        assert result["skills_used"] == []
        assert result["routing_path"] == []
        assert result["errors"] == []
        assert result["risk_flags"] == []

    def test_collect_none_result(self):
        mc = MetricsCollector()
        result = mc.collect()
        assert result["skills_used"] == []
        assert result["token_usage"] == 0

    def test_collect_with_errors(self):
        mc = MetricsCollector()
        result = mc.collect(kernel_result=_make_kernel_result(steps=[
            {"step_id": 1, "action": "test", "tool": "code",
             "tool_input": "x", "tool_output": "[工具错误] code: fail"},
        ]))
        # Has 1 error step but execution_report builder extracts errors,
        # metrics itself collects structure
        assert len(result["skills_used"]) == 1

    def test_token_estimation(self):
        mc = MetricsCollector()
        result = mc.collect(kernel_result=_make_kernel_result(goal="a" * 100))
        assert result["token_usage"] > 0

    def test_risk_flags_from_insight(self):
        mc = MetricsCollector()
        result = mc.collect(
            kernel_result=_make_kernel_result(),
            insight_report={
                "health_status": "degraded",
                "drift": {"drift_detected": True},
            },
        )
        assert "drift_detected" in result["risk_flags"]
        assert "system_degraded" in result["risk_flags"]

    def test_risk_flags_unstable(self):
        mc = MetricsCollector()
        result = mc.collect(
            kernel_result=_make_kernel_result(),
            insight_report={"health_status": "unstable"},
        )
        assert "system_unstable" in result["risk_flags"]


# ─── ExecutionReport ──────────────────────────────────────────────────────────

class TestExecutionReport:
    def test_default_report(self):
        r = ExecutionReport()
        assert r.skills_used == []
        assert r.risk_flags == []
        assert r.success

    def test_to_dict(self):
        r = ExecutionReport(task_id="t1")
        d = r.to_dict()
        assert d["task_id"] == "t1"

    def test_to_json(self):
        r = ExecutionReport(task_id="t1", task_input="测试")
        j = r.to_json()
        assert "t1" in j
        assert "测试" in j
        json.loads(j)  # 确保有效 JSON

    def test_populated_report_to_json(self):
        r = ExecutionReport(
            task_id="t2",
            skills_used=["llm"],
            routing_path=["llm", "code"],
            token_usage=100,
            system_health="healthy",
        )
        d = r.to_dict()
        assert d["skills_used"] == ["llm"]
        assert d["system_health"] == "healthy"


# ─── ExecutionReportBuilder ───────────────────────────────────────────────────

class TestExecutionReportBuilder:
    def test_build_from_complete_result(self):
        builder = ExecutionReportBuilder()
        report = builder.from_kernel_result(result=_make_kernel_result())
        assert report.task_id == "task-1"
        assert report.success
        assert len(report.steps) == 2
        assert "code" in report.skills_used
        assert "llm" in report.skills_used
        assert report.system_health == "healthy"
        assert report.timestamp != ""

    def test_build_from_empty_result(self):
        builder = ExecutionReportBuilder()
        report = builder.from_kernel_result(result=None)
        assert report.summary == "无执行数据"

    def test_build_with_failed_status(self):
        builder = ExecutionReportBuilder()
        report = builder.from_kernel_result(result=_make_kernel_result(status="failed"))
        assert not report.success

    def test_build_with_insight(self):
        builder = ExecutionReportBuilder()
        report = builder.from_kernel_result(
            result=_make_kernel_result(),
            insight_report={
                "health_status": "degraded",
                "summary": "部分指标异常",
                "drift": {"drift_detected": False},
            },
        )
        assert report.system_health == "degraded"
        assert "部分指标异常" in report.insight_summary

    def test_error_detection_in_steps(self):
        builder = ExecutionReportBuilder()
        report = builder.from_kernel_result(result=_make_kernel_result(steps=[
            {"step_id": 1, "action": "test", "tool": "code",
             "tool_input": "x", "tool_output": "[工具错误] code: fail"},
            {"step_id": 2, "action": "test2", "tool": "llm",
             "tool_input": "y", "tool_output": "[工具不可用] llm"},
        ]))
        assert len(report.errors) == 2


# ─── ReportFormatter ──────────────────────────────────────────────────────────

class TestReportFormatter:
    def _make_report(self, **kw):
        # 默认值，允许 overrides 覆盖
        defaults = dict(
            task_id="t1",
            task_input="测试任务",
            success=True,
            steps=[
                {"step_id": 1, "action": "run code", "tool": "code"},
                {"step_id": 2, "action": "ask llm", "tool": "llm"},
            ],
            skills_used=["code", "llm"],
            routing_path=["code", "llm"],
            token_usage=50,
            system_health="healthy",
        )
        defaults.update(kw)
        return ExecutionReport(**defaults)

    def test_to_text_contains_sections(self):
        f = ReportFormatter()
        text = f.to_text(self._make_report())
        assert "DVexa Execution Report" in text
        assert "Task:" in text
        assert "Execution" in text
        assert "Skills" in text
        assert "Routing Path" in text
        assert "Metrics" in text

    def test_to_text_with_errors(self):
        f = ReportFormatter()
        text = f.to_text(self._make_report(errors=["step 1: fail"]))
        assert "Errors" in text
        assert "fail" in text

    def test_to_text_with_risk_flags(self):
        f = ReportFormatter()
        text = f.to_text(self._make_report(risk_flags=["high_error_rate"]))
        assert "Risk Flags" in text
        assert "high_error_rate" in text

    def test_to_text_failed_task(self):
        f = ReportFormatter()
        text = f.to_text(self._make_report(success=False))
        assert "失败" in text

    def test_to_text_no_steps(self):
        f = ReportFormatter()
        report = self._make_report(steps=[], skills_used=[], routing_path=[])
        text = f.to_text(report)
        assert "(no steps)" in text

    def test_to_summary(self):
        f = ReportFormatter()
        summary = f.to_summary(self._make_report())
        assert "测试任务" in summary
        assert "healthy" in summary
        assert "2 steps" in summary
        assert "50 tokens" in summary

    def test_to_summary_failed(self):
        f = ReportFormatter()
        summary = f.to_summary(self._make_report(success=False))
        assert "✗" in summary

    def test_to_json_valid(self):
        f = ReportFormatter()
        j = f.to_json(self._make_report())
        data = json.loads(j)
        assert data["task_id"] == "t1"
        assert data["system_health"] == "healthy"

    def test_to_text_with_governance_changes(self):
        f = ReportFormatter()
        report = self._make_report(
            governance_changes=[{"skill": "http", "from": "active", "to": "degraded"}],
        )
        text = f.to_text(report)
        assert "Governance" in text
