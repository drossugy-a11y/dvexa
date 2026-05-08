"""Tests for ATS v1.2 — Assimilation Test System"""

import pytest
from governance.assimilation_test_system import (
    AssimilationTestSystem,
    SafetyChecker,
    ATCapabilityMapper,
    RiskAssessor,
    DecisionEngine,
    ATSReport,
    ATSPhaseResult,
    ATSVerdict,
    RiskLevel,
)


class TestSafetyChecker:
    """测试安全检查"""

    def setup_method(self):
        self.checker = SafetyChecker()

    def test_safe_target(self):
        result = self.checker.check("scanner")
        assert result.passed is True
        assert result.verdict == ATSVerdict.PASS

    def test_empty_target(self):
        result = self.checker.check("")
        assert result.passed is False
        assert result.verdict == ATSVerdict.FAIL

    def test_blocked_core_target(self):
        result = self.checker.check("core")
        assert result.passed is False
        assert result.verdict == ATSVerdict.FAIL

    def test_blocked_kernel_target(self):
        result = self.checker.check("kernel")
        assert result.passed is False

    def test_blocked_executor(self):
        result = self.checker.check("executor")
        assert result.passed is False

    def test_blocked_guard(self):
        result = self.checker.check("guard")
        assert result.passed is False

    def test_blocked_base_agent(self):
        result = self.checker.check("base_agent")
        assert result.passed is False

    def test_dangerous_keyword_warning(self):
        result = self.checker.check("bypass_module")
        assert result.passed is True
        assert result.verdict == ATSVerdict.WARN
        assert len(result.warnings) >= 1

    def test_multiple_dangerous_keywords(self):
        result = self.checker.check("bypass_inject_hack")
        assert len(result.warnings) >= 3


class TestATCapabilityMapper:
    """测试能力映射"""

    def setup_method(self):
        self.mapper = ATCapabilityMapper()

    def test_map_scanner(self):
        result = self.mapper.map("port_scanner")
        assert result.passed is True
        assert "scanner" in result.details

    def test_map_analyzer(self):
        result = self.mapper.map("data_analyzer")
        assert result.passed is True
        assert "analyzer" in result.details

    def test_map_loader(self):
        result = self.mapper.map("config_loader")
        assert result.passed is True
        assert "loader" in result.details

    def test_map_exporter(self):
        result = self.mapper.map("log_exporter")
        assert result.passed is True
        assert "exporter" in result.details

    def test_map_monitor(self):
        result = self.mapper.map("system_monitor")
        assert result.passed is True
        assert "monitor" in result.details

    def test_map_unknown(self):
        result = self.mapper.map("random_name")
        assert result.passed is True
        assert result.verdict == ATSVerdict.WARN
        assert len(result.warnings) >= 1

    def test_map_empty(self):
        result = self.mapper.map("")
        assert result.passed is True
        assert result.verdict == ATSVerdict.WARN


class TestRiskAssessor:
    """测试风险评估"""

    def setup_method(self):
        self.assessor = RiskAssessor()

    def test_low_risk_empty_name(self):
        score = self.assessor.assess("scanner", [])
        assert 0.0 <= score <= 0.2
        assert self.assessor.get_risk_level(score) == RiskLevel.LOW

    def test_medium_risk_external_keyword(self):
        score = self.assessor.assess("external_service", [])
        assert 0.1 <= score <= 0.2
        assert self.assessor.get_risk_level(score) in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_high_risk_internal_keyword(self):
        score = self.assessor.assess("internal_service", [])
        assert score >= 0.3
        assert self.assessor.get_risk_level(score) == RiskLevel.HIGH

    def test_risk_increases_with_warnings(self):
        clean = self.assessor.assess("scanner", [])
        warnings = [
            ATSPhaseResult(phase="test", passed=True, verdict=ATSVerdict.WARN,
                           warnings=["w1"]),
        ]
        with_warning = self.assessor.assess("scanner", warnings)
        assert with_warning > clean

    def test_risk_increases_with_failures(self):
        clean = self.assessor.assess("scanner", [])
        failed = [
            ATSPhaseResult(phase="test", passed=False, verdict=ATSVerdict.FAIL),
        ]
        with_fail = self.assessor.assess("scanner", failed)
        assert with_fail > clean

    def test_risk_capped_at_one(self):
        score = self.assessor.assess(
            "internal_core_admin_bypass",
            [
                ATSPhaseResult(phase="a", passed=False, verdict=ATSVerdict.FAIL),
                ATSPhaseResult(phase="b", passed=False, verdict=ATSVerdict.FAIL),
                ATSPhaseResult(phase="c", passed=False, verdict=ATSVerdict.FAIL),
                ATSPhaseResult(phase="d", passed=False, verdict=ATSVerdict.FAIL),
                ATSPhaseResult(phase="e", passed=False, verdict=ATSVerdict.FAIL),
                ATSPhaseResult(phase="f", passed=True, verdict=ATSVerdict.WARN,
                               warnings=["w"] * 5),
            ],
        )
        assert score <= 1.0

    def test_risk_level_thresholds(self):
        assert self.assessor.get_risk_level(0.0) == RiskLevel.LOW
        assert self.assessor.get_risk_level(0.14) == RiskLevel.LOW
        assert self.assessor.get_risk_level(0.15) == RiskLevel.MEDIUM
        assert self.assessor.get_risk_level(0.29) == RiskLevel.MEDIUM
        assert self.assessor.get_risk_level(0.3) == RiskLevel.HIGH
        assert self.assessor.get_risk_level(0.69) == RiskLevel.HIGH
        assert self.assessor.get_risk_level(0.7) == RiskLevel.CRITICAL
        assert self.assessor.get_risk_level(1.0) == RiskLevel.CRITICAL

    def test_sgl_risk_elevates_ats_risk(self):
        """SGL risk score should be incorporated into ATS risk."""
        score = self.assessor.assess("scanner", [], sgl_risk_score=0.9)
        assert score >= 0.9  # Should be at least as high as SGL risk
        assert score <= 1.0  # Should still be capped


class TestDecisionEngine:
    """测试决策引擎"""

    def setup_method(self):
        self.engine = DecisionEngine()

    def test_all_pass_allows(self):
        report = ATSReport(
            target="test",
            passed=True,
            phases=[ATSPhaseResult("a", True, ATSVerdict.PASS)],
            risk_level=RiskLevel.LOW,
        )
        assert self.engine.decide(report) is True

    def test_fail_blocks(self):
        report = ATSReport(
            target="test",
            passed=False,
            phases=[ATSPhaseResult("a", False, ATSVerdict.FAIL)],
            risk_level=RiskLevel.LOW,
        )
        assert self.engine.decide(report) is False

    def test_critical_risk_blocks(self):
        report = ATSReport(
            target="test",
            passed=False,
            phases=[ATSPhaseResult("a", True, ATSVerdict.PASS)],
            risk_level=RiskLevel.CRITICAL,
            risk_score=0.8,
        )
        assert self.engine.decide(report) is False

    def test_decide_with_reason_approved(self):
        report = ATSReport(
            target="test",
            passed=True,
            phases=[ATSPhaseResult("a", True, ATSVerdict.PASS)],
            risk_level=RiskLevel.LOW,
        )
        result = self.engine.decide_with_reason(report)
        assert result["allowed"] is True
        assert result["verdict"] == "approved"

    def test_decide_with_reason_rejected(self):
        report = ATSReport(
            target="test",
            passed=False,
            phases=[ATSPhaseResult("a", False, ATSVerdict.FAIL)],
            risk_level=RiskLevel.CRITICAL,
            risk_score=0.9,
        )
        result = self.engine.decide_with_reason(report)
        assert result["allowed"] is False
        assert result["verdict"] == "rejected"
        assert len(result["reasons"]) >= 1


class TestATSIntegration:
    """ATS 完整流水线集成测试"""

    def setup_method(self):
        self.ats = AssimilationTestSystem()

    def test_run_safe_scanner(self):
        report = self.ats.run("scanner", {"intent": "analysis"})
        assert report.passed is True
        assert report.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)
        assert report.phase_count == 7

    def test_run_safe_loader(self):
        report = self.ats.run("config_loader", {"intent": "analysis"})
        assert report.passed is True
        assert report.phase_count == 7

    def test_run_blocked_core(self):
        report = self.ats.run("core", {"intent": "analysis"})
        assert report.passed is False
        # 解析通过但安全检查失败
        assert report.failed_phases >= 1

    def test_run_manipulation_intent(self):
        report = self.ats.run("scanner", {"intent": "manipulation"})
        assert report.passed is True  # warning but not fail
        # governance phase should have warning
        gov_phase = [p for p in report.phases if p.phase == "governance"][0]
        assert len(gov_phase.warnings) >= 1

    def test_run_with_write_constraint(self):
        report = self.ats.run("file_writer", {
            "intent": "execution",
            "constraint": "write access needed",
        })
        assert report.passed is True
        # simulation phase should warn about write
        sim_phase = [p for p in report.phases if p.phase == "simulation"][0]
        assert len(sim_phase.warnings) >= 1

    def test_run_empty_target_fails_parse(self):
        report = self.ats.run("", {})
        assert report.passed is False
        assert report.failed_phases >= 1

    def test_run_dangerous_target(self):
        report = self.ats.run("bypass_scanner", {"intent": "analysis"})
        assert report.passed is True  # warning only, not fail
        safety_phase = [p for p in report.phases if p.phase == "safety"][0]
        assert safety_phase.verdict == ATSVerdict.WARN

    def test_decisions_phase_present(self):
        report = self.ats.run("analyzer", {"intent": "analysis"})
        decision_phase = [p for p in report.phases if p.phase == "decision"][0]
        assert decision_phase.passed is True

    def test_report_properties(self):
        report = self.ats.run("external_monitor", {"intent": "extraction"})
        assert report.phase_count == 7
        assert report.passed_phases <= report.phase_count
        assert isinstance(report.all_warnings, list)

    def test_ats_report_consistency(self):
        """所有报告的 passed_phases + failed_phases == phase_count"""
        report = self.ats.run("scanner", {"intent": "analysis"})
        assert report.passed_phases + report.failed_phases == report.phase_count

    def test_context_sgl_risk_incorporated(self):
        """SGL risk passed via context should affect ATS final report."""
        report = self.ats.run("test_target", {"sgl_risk_score": 0.9})
        assert report.risk_score >= 0.9
        assert report.risk_level.value in ("critical",)


class TestATSReport:
    """测试 ATSReport 数据类"""

    def test_empty_report_defaults(self):
        report = ATSReport(target="test", passed=True)
        assert report.phase_count == 0
        assert report.passed_phases == 0
        assert report.failed_phases == 0
        assert report.all_warnings == []
        assert report.risk_score == 0.0
        assert report.risk_level == RiskLevel.LOW
        assert report.summary == ""

    def test_report_with_phases(self):
        report = ATSReport(
            target="test",
            passed=True,
            phases=[
                ATSPhaseResult("a", True, ATSVerdict.PASS),
                ATSPhaseResult("b", False, ATSVerdict.FAIL),
                ATSPhaseResult("c", True, ATSVerdict.WARN, warnings=["w1"]),
            ],
        )
        assert report.phase_count == 3
        assert report.passed_phases == 2
        assert report.failed_phases == 1
        assert report.all_warnings == ["w1"]


class TestATSPrintReport:
    """测试报告输出格式"""

    def setup_method(self):
        self.ats = AssimilationTestSystem()

    def test_print_report_contains_target(self):
        report = self.ats.run("scanner", {"intent": "analysis"})
        output = self.ats.print_report(report)
        assert "scanner" in output
        assert "PASS" in output or "FAIL" in output

    def test_print_report_contains_phases(self):
        report = self.ats.run("analyzer", {"intent": "extraction"})
        output = self.ats.print_report(report)
        assert "parse" in output.lower()
        assert "safety" in output.lower()
        assert "mapping" in output.lower()
        assert "governance" in output.lower()
        assert "risk" in output.lower()
        assert "simulation" in output.lower()
        assert "decision" in output.lower()

    def test_print_report_contains_warnings(self):
        report = self.ats.run("bypass_attempt", {"intent": "analysis"})
        output = self.ats.print_report(report)
        assert "bypass" in output.lower() or "⚠" in output

    def test_print_report_empty_target(self):
        report = self.ats.run("", {})
        output = self.ats.print_report(report)
        assert "FAIL" in output


class TestATSPhaseResult:
    """测试 ATSPhaseResult 数据类"""

    def test_phase_result_defaults(self):
        result = ATSPhaseResult(phase="test", passed=True, verdict=ATSVerdict.PASS)
        assert result.details == ""
        assert result.warnings == []

    def test_phase_result_with_details(self):
        result = ATSPhaseResult(
            phase="test", passed=False, verdict=ATSVerdict.FAIL,
            details="Something went wrong",
            warnings=["error 1", "error 2"],
        )
        assert result.details == "Something went wrong"
        assert len(result.warnings) == 2
