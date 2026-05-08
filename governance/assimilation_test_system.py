"""ATS v1.2 — Assimilation Test System

定位：位于 SGL(语义判断) 和 AssimilationScheduler(吞并节奏) 之间的行为验证层。
职责：在吞并进入调度器之前，验证能力是否可安全同化。

7-Phase Pipeline:
  Parse → Safety → Mapping → Governance → Risk → Simulation → Decision

红线：
  - 不修改任何系统状态
  - 不执行任何代码
  - 不调用 SkillRegistry/SkillGovernor
  - 纯观察 + 分析
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


# ─── Types ─────────────────────────────────────────────────────────────────────

class ATSVerdict(enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class RiskLevel(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ATSPhaseResult:
    """单个阶段的分析结果。"""
    phase: str
    passed: bool
    verdict: ATSVerdict
    details: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class ATSReport:
    """ATS 完整分析报告。"""
    target: str
    passed: bool
    phases: list[ATSPhaseResult] = field(default_factory=list)
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    summary: str = ""

    @property
    def phase_count(self) -> int:
        return len(self.phases)

    @property
    def passed_phases(self) -> int:
        return sum(1 for p in self.phases if p.passed)

    @property
    def failed_phases(self) -> int:
        return sum(1 for p in self.phases if not p.passed)

    @property
    def all_warnings(self) -> list[str]:
        warnings: list[str] = []
        for phase in self.phases:
            warnings.extend(phase.warnings)
        return warnings


# ─── Safety Checker ────────────────────────────────────────────────────────────

class SafetyChecker:
    """Phase 2: 安全检查 — 验证模块名是否合规、是否有危险模式。"""

    # 禁止的模块名模式
    BLOCKED_TARGET_PATTERNS = [
        "core", "kernel", "executor", "guard", "base_agent",
    ]

    # 危险关键词（出现在 target 名称中时报警）
    DANGEROUS_TARGET_KEYWORDS = [
        "bypass", "override", "inject", "hack", "exploit",
        "绕过", "注入", "提权", "root",
    ]

    def check(self, target: str) -> ATSPhaseResult:
        """检查目标模块是否安全。"""
        target_lower = target.lower().strip()
        warnings: list[str] = []

        if not target_lower:
            return ATSPhaseResult(
                phase="safety",
                passed=False,
                verdict=ATSVerdict.FAIL,
                details="Target name is empty",
            )

        if target_lower in self.BLOCKED_TARGET_PATTERNS:
            return ATSPhaseResult(
                phase="safety",
                passed=False,
                verdict=ATSVerdict.FAIL,
                details=f"Target '{target}' is a blocked system component",
            )

        # 检查危险关键词
        for kw in self.DANGEROUS_TARGET_KEYWORDS:
            if kw in target_lower:
                warnings.append(f"Target name contains dangerous keyword '{kw}'")

        if warnings:
            return ATSPhaseResult(
                phase="safety",
                passed=True,
                verdict=ATSVerdict.WARN,
                details=f"Target '{target}' passed safety check with warnings",
                warnings=warnings,
            )

        return ATSPhaseResult(
            phase="safety",
            passed=True,
            verdict=ATSVerdict.PASS,
            details=f"Target '{target}' is safe",
        )


# ─── Capability Mapper (Phase 3) ──────────────────────────────────────────────

class ATCapabilityMapper:
    """Phase 3: 能力映射 — 验证目标是否可以映射到已知能力类型。

    注意：此为纯规则匹配，不访问 SkillRegistry。
    """

    # 能力类型关键词映射
    CAPABILITY_PATTERNS: dict[str, list[str]] = {
        "scanner": ["scan", "scanner", "scanning"],
        "analyzer": ["analyzer", "analysis", "analyze"],
        "collector": ["collect", "collector", "gather", "harvest"],
        "loader": ["load", "loader", "import"],
        "exporter": ["export", "exporter", "dump"],
        "monitor": ["monitor", "watch", "observer"],
        "transformer": ["transform", "converter", "convert", "format"],
    }

    def map(self, target: str) -> ATSPhaseResult:
        """将目标映射到能力类型。"""
        target_lower = target.lower()
        matched_types: list[str] = []

        for cap_type, keywords in self.CAPABILITY_PATTERNS.items():
            if any(kw in target_lower for kw in keywords):
                matched_types.append(cap_type)

        if not matched_types:
            return ATSPhaseResult(
                phase="mapping",
                passed=True,
                verdict=ATSVerdict.WARN,
                details=f"Target '{target}' does not match any known capability type",
                warnings=[f"Unknown capability type for '{target}'"],
            )

        return ATSPhaseResult(
            phase="mapping",
            passed=True,
            verdict=ATSVerdict.PASS,
            details=f"Target '{target}' maps to capabilities: {', '.join(matched_types)}",
        )


# ─── Risk Assessor (Phase 5) ───────────────────────────────────────────────────

class RiskAssessor:
    """Phase 5: 风险评估 — 综合评估吞并风险。"""

    # 高风险目标关键词
    HIGH_RISK_KEYWORDS = [
        "internal", "system", "core", "privileged", "admin",
        "内部", "系统", "核心", "管理",
    ]

    # 中风险目标关键词
    MEDIUM_RISK_KEYWORDS = [
        "external", "network", "service", "daemon", "agent",
        "外部", "网络", "服务",
    ]

    def assess(
        self,
        target: str,
        phase_results: list[ATSPhaseResult],
        sgl_risk_score: float = 0.0,
    ) -> float:
        """计算风险评分 [0.0, 1.0]。

        评分因素：
          - 目标名称中的风险关键词
          - 各阶段警告数量
          - 失败阶段数量
          - SGL 风险评分（来自语义判断层）
        """
        target_lower = target.lower()
        risk = 0.0

        # 目标关键词风险
        if any(kw in target_lower for kw in self.HIGH_RISK_KEYWORDS):
            risk += 0.3
        elif any(kw in target_lower for kw in self.MEDIUM_RISK_KEYWORDS):
            risk += 0.15

        # 每个警告 +0.05
        warning_count = sum(len(p.warnings) for p in phase_results)
        risk += 0.05 * warning_count

        # 每个失败阶段 +0.1
        fail_count = sum(1 for p in phase_results if not p.passed)
        risk += 0.1 * fail_count

        # SGL 风险合并：取两者中的较高值
        risk = max(risk, sgl_risk_score)

        return min(risk, 1.0)

    def get_risk_level(self, score: float) -> RiskLevel:
        if score >= 0.7:
            return RiskLevel.CRITICAL
        elif score >= 0.3:
            return RiskLevel.HIGH
        elif score >= 0.15:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW


# ─── Decision Engine (Phase 7) ────────────────────────────────────────────────

class DecisionEngine:
    """Phase 7: 决策引擎 — 基于各阶段结果和风险评分做出最终决定。"""

    def decide(self, report: ATSReport) -> bool:
        """返回 True = 允许吞并，False = 拒绝吞并。"""
        # 任何 FAIL 都拒绝
        if any(not p.passed for p in report.phases):
            return False
        # CRITICAL 风险拒绝
        if report.risk_level == RiskLevel.CRITICAL:
            return False
        return True

    def decide_with_reason(self, report: ATSReport) -> dict:
        """返回详细决策结果。"""
        allowed = self.decide(report)
        reasons: list[str] = []

        if any(not p.passed for p in report.phases):
            failed = [p.phase for p in report.phases if not p.passed]
            reasons.append(f"Phase(s) failed: {', '.join(failed)}")
        if report.risk_level == RiskLevel.CRITICAL:
            reasons.append(f"Risk level is CRITICAL ({report.risk_score})")

        if allowed:
            return {
                "allowed": True,
                "verdict": "approved",
                "reasons": reasons or ["All checks passed"],
            }
        else:
            return {
                "allowed": False,
                "verdict": "rejected",
                "reasons": reasons or ["Unknown failure"],
            }


# ─── ATS Main Pipeline ────────────────────────────────────────────────────────

class AssimilationTestSystem:
    """ATS 主入口 — 执行 7 阶段吞并测试流水线。

    Usage:
        ats = AssimilationTestSystem()
        report = ats.run("scanner", {"intent": "analysis"})
        ats.print_report(report)
    """

    def __init__(self):
        self._safety = SafetyChecker()
        self._mapper = ATCapabilityMapper()
        self._risk = RiskAssessor()
        self._decision = DecisionEngine()

    def run_event(self, event: "Event") -> "Event":
        """Event Transformer: input Event → output Event。

        将 run() 的输出包装为 Event，不修改内部逻辑。
        """
        from runtime.event import Event as RuntimeEvent
        target = event.payload.get("target", "")
        context = event.payload.get("context", {})
        report = self.run(target, context)
        return RuntimeEvent(
            trace_id=event.trace_id,
            stage="validate",
            event_type="decision",
            payload={
                "target": report.target,
                "passed": report.passed,
                "risk_score": report.risk_score,
                "risk_level": report.risk_level.value if hasattr(report.risk_level, "value") else str(report.risk_level),
                "phase_count": report.phase_count,
                "passed_phases": report.passed_phases,
                "failed_phases": report.failed_phases,
                "summary": report.summary,
                "phases": [
                    {"phase": p.phase, "passed": p.passed, "verdict": str(p.verdict), "details": p.details}
                    for p in report.phases
                ],
            },
            metadata={"input_event_id": event.trace_id},
        )

    def run(
        self,
        target: str,
        context: dict[str, Any] | None = None,
    ) -> ATSReport:
        """执行完整 7 阶段吞并测试。

        Args:
            target: 目标模块名称
            context: 上下文信息（可选），如 {"intent": "analysis", "mode": "observe"}

        Returns:
            ATSReport: 完整测试报告
        """
        context = context or {}
        phases: list[ATSPhaseResult] = []

        # Phase 1: Parse — 解析输入
        parse_result = self._phase_parse(target, context)
        phases.append(parse_result)

        # 如果解析失败，后续阶段跳过
        if not parse_result.passed:
            return self._finalize(target, phases)

        # Phase 2: Safety — 安全检查
        safety_result = self._safety.check(target)
        phases.append(safety_result)

        # Phase 3: Mapping — 能力映射
        mapping_result = self._mapper.map(target)
        phases.append(mapping_result)

        # Phase 4: Governance — 治理检查（占位，SGL 层已完成语义治理）
        governance_result = self._phase_governance(context)
        phases.append(governance_result)

        # Phase 5: Risk — 风险评估（纳入 SGL 风险评分）
        sgl_risk_score = context.get("sgl_risk_score", 0.0)
        risk_score = self._risk.assess(target, phases, sgl_risk_score=sgl_risk_score)
        risk_level = self._risk.get_risk_level(risk_score)
        risk_result = ATSPhaseResult(
            phase="risk",
            passed=True,
            verdict=ATSVerdict.PASS,
            details=f"Risk score: {risk_score}, level: {risk_level.value}",
        )
        phases.append(risk_result)

        # Phase 6: Simulation — 模拟执行（纯检查，不真实执行）
        sim_result = self._phase_simulation(target, context)
        phases.append(sim_result)

        # Phase 7: Decision — 决策
        report = self._finalize(target, phases, risk_score, risk_level)
        decision_result = self._decision.decide_with_reason(report)
        decision_phase = ATSPhaseResult(
            phase="decision",
            passed=decision_result["allowed"],
            verdict=ATSVerdict.PASS if decision_result["allowed"] else ATSVerdict.FAIL,
            details=decision_result["verdict"] + ": " + "; ".join(decision_result["reasons"]),
        )
        phases.append(decision_phase)

        return self._finalize(target, phases, risk_score, risk_level)

    def _phase_parse(
        self, target: str, context: dict[str, Any]
    ) -> ATSPhaseResult:
        """Phase 1: 解析输入。"""
        if not target or not target.strip():
            return ATSPhaseResult(
                phase="parse",
                passed=False,
                verdict=ATSVerdict.FAIL,
                details="Target is empty",
            )
        if not isinstance(target, str):
            return ATSPhaseResult(
                phase="parse",
                passed=False,
                verdict=ATSVerdict.FAIL,
                details=f"Target must be a string, got {type(target).__name__}",
            )
        return ATSPhaseResult(
            phase="parse",
            passed=True,
            verdict=ATSVerdict.PASS,
            details=f"Parsed target '{target}' with context keys: {list(context.keys())}",
        )

    def _phase_governance(
        self, context: dict[str, Any]
    ) -> ATSPhaseResult:
        """Phase 4: 治理检查（占位 — SGL 已完成语义治理）。"""
        intent = context.get("intent", "unknown")
        if intent == "manipulation":
            return ATSPhaseResult(
                phase="governance",
                passed=True,
                verdict=ATSVerdict.WARN,
                details="Manipulation intent detected, deferring to SGL decision",
                warnings=["Manipulation intent requires additional scrutiny"],
            )
        return ATSPhaseResult(
            phase="governance",
            passed=True,
            verdict=ATSVerdict.PASS,
            details=f"Intent '{intent}' accepted",
        )

    def _phase_simulation(
        self, target: str, context: dict[str, Any]
    ) -> ATSPhaseResult:
        """Phase 6: 模拟执行（纯检查，不真实执行）。"""
        # 检查 context 中的 constraint
        constraint = context.get("constraint", "")
        if "write" in constraint.lower() or "modify" in constraint.lower():
            return ATSPhaseResult(
                phase="simulation",
                passed=True,
                verdict=ATSVerdict.WARN,
                details=f"Target '{target}' requests write access",
                warnings=["Write/modify access requires confirmation"],
            )
        return ATSPhaseResult(
            phase="simulation",
            passed=True,
            verdict=ATSVerdict.PASS,
            details=f"Target '{target}' simulation completed (read-only)",
        )

    def _finalize(
        self,
        target: str,
        phases: list[ATSPhaseResult],
        risk_score: float = 0.0,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> ATSReport:
        """构建最终报告。"""
        passed = all(p.passed for p in phases) and risk_level != RiskLevel.CRITICAL
        fail_count = sum(1 for p in phases if not p.passed)
        warn_count = sum(len(p.warnings) for p in phases)

        summary_parts = []
        if passed:
            summary_parts.append("PASSED")
        else:
            summary_parts.append("FAILED")
        summary_parts.append(f"{fail_count} failed")
        summary_parts.append(f"{warn_count} warnings")
        summary_parts.append(f"risk {risk_level.value} ({risk_score})")

        return ATSReport(
            target=target,
            passed=passed,
            phases=phases,
            risk_score=risk_score,
            risk_level=risk_level,
            summary=" | ".join(summary_parts),
        )

    def print_report(self, report: ATSReport) -> str:
        """生成可读的报告字符串。"""
        lines = [
            f"ATS Report: {report.target}",
            f"Overall: {'PASS' if report.passed else 'FAIL'}",
            f"Risk: {report.risk_level.value} ({report.risk_score})",
            f"Phases: {report.passed_phases}/{report.phase_count} passed",
            "",
        ]
        for phase in report.phases:
            status = "PASS" if phase.passed else "FAIL"
            lines.append(f"  [{status}] {phase.phase}: {phase.details}")
            for w in phase.warnings:
                lines.append(f"         ⚠ {w}")

        if report.all_warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in report.all_warnings:
                lines.append(f"  - {w}")

        return "\n".join(lines)
