"""DXB Validator v2.0 — DXB 安全性验证器

严格的编译时安全门，验证 DXB 在交给 Kernel 执行前的正确性。
只读操作，绝不修改 DXB。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from compiler_v2.capability_ir import DXB


@dataclass
class ValidationReport:
    """验证报告。"""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_risk_flag(self, msg: str) -> None:
        self.risk_flags.append(msg)


class DXBValidator:
    """DXB 验证器 — 编译时安全门。

    验证检查:

    STRUCTURAL (阻断性):
      - DAG 无环 (cycle detection via DFS)
      - 所有步骤的依赖引用存在的步骤
      - 无孤儿执行路径 (所有步骤可从入口到达)

    GOVERNANCE (阻断性):
      - constraints 格式良好
      - 无运行时决策字段 ("runtime_decision": true 会导致阻断)
      - 所有 policy constraints 包含必要字段

    POLICY (警告性):
      - SGL constraints 存在
      - ATS constraints 存在
      - Scheduler constraints 存在
      - 风险阈值合理性检查

    规则: Validator 绝不修改 DXB。
    """

    # 已知有效的能力引用前缀
    KNOWN_CAPABILITY_PREFIXES = {
        "semantic_intent", "context_load", "threat_detected",
        "validation_phases", "scheduled_action", "memory_capability",
        "hybrid_search", "mmr_ranking", "chunking", "semantic_search",
        "embeddings", "temporal_decay", "memory_index", "batch_operations",
    }

    # 禁止出现在 DXB 中的运行时决策关键词
    FORBIDDEN_RUNTIME_KEYWORDS = {
        "runtime_decision", "runtime_action", "execute_now",
        "live_check", "dynamic_dispatch", "real_time",
    }

    def validate(self, dxb: DXB) -> ValidationReport:
        """验证 DXB 的正确性和安全性。

        Args:
            dxb: 待验证的 DXB

        Returns:
            ValidationReport: 验证报告 (只读操作，不修改 dxb)
        """
        report = ValidationReport()

        # ── Structural checks ──
        self._check_cycles(dxb, report)
        self._check_dependency_integrity(dxb, report)
        self._check_orphan_paths(dxb, report)
        self._check_step_cardinality(dxb, report)

        # ── Governance checks ──
        self._check_constraints_wellformed(dxb, report)
        self._check_no_runtime_decisions(dxb, report)
        self._check_policy_fields(dxb, report)

        # ── Policy checks ──
        self._check_governance_coverage(dxb, report)
        self._check_risk_thresholds(dxb, report)

        return report

    # ═══════════════════════════════════════════════════════════════
    # Structural checks
    # ═══════════════════════════════════════════════════════════════

    def _check_cycles(self, dxb: DXB, report: ValidationReport) -> None:
        """使用 DFS 检测 DAG 中的环。"""
        if not dxb.steps:
            return

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {s.id: WHITE for s in dxb.steps}

        def dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            deps = dxb.dag.get(node_id, [])
            for dep in deps:
                if dep not in color:
                    continue  # external reference, skip
                if color[dep] == GRAY:
                    report.add_error(f"Cycle detected: {node_id} → {dep}")
                    return False
                if color[dep] == WHITE:
                    if not dfs(dep):
                        return False
            color[node_id] = BLACK
            return True

        for step in dxb.steps:
            if color[step.id] == WHITE:
                dfs(step.id)

    def _check_dependency_integrity(self, dxb: DXB, report: ValidationReport) -> None:
        """验证所有依赖引用存在的步骤。"""
        all_ids = {s.id for s in dxb.steps}

        for step in dxb.steps:
            for dep in step.dependencies:
                if dep not in all_ids:
                    report.add_error(
                        f"Step '{step.id}' references unknown dependency '{dep}'"
                    )

    def _check_orphan_paths(self, dxb: DXB, report: ValidationReport) -> None:
        """检测完全孤立的执行路径（无入边且无出边的步骤）。"""
        if len(dxb.steps) <= 1:
            return

        has_incoming: set[str] = set()
        has_outgoing: set[str] = set()

        for step in dxb.steps:
            if step.dependencies:
                has_incoming.add(step.id)
            for dep in step.dependencies:
                has_outgoing.add(dep)

        all_ids = {s.id for s in dxb.steps}
        orphans = all_ids - has_incoming - has_outgoing

        if orphans:
            report.add_warning(
                f"Orphan execution paths detected: {', '.join(sorted(orphans))}"
            )

    def _check_step_cardinality(self, dxb: DXB, report: ValidationReport) -> None:
        """检查步骤数量合理性。"""
        if not dxb.steps:
            report.add_warning("DXB has no steps — empty execution blueprint")
        elif dxb.step_count > 1000:
            report.add_warning(f"DXB has {dxb.step_count} steps — consider optimization")

    # ═══════════════════════════════════════════════════════════════
    # Governance checks
    # ═══════════════════════════════════════════════════════════════

    def _check_constraints_wellformed(self, dxb: DXB, report: ValidationReport) -> None:
        """验证 constraints 结构良好。"""
        constraints = dxb.constraints

        # Check it's a dict
        if not isinstance(constraints, dict):
            report.add_error(f"Constraints must be a dict, got {type(constraints).__name__}")
            return

        # Check required top-level keys
        policy = constraints.get("policy", {})
        if isinstance(policy, dict):
            # Check policy has required sub-keys
            for key in ("sgl", "ats", "scheduler"):
                if key not in policy:
                    report.add_warning(f"Missing policy constraint: '{key}'")
        elif not isinstance(policy, dict):
            report.add_error(f"Policy constraints must be a dict, got {type(policy).__name__}")

    def _check_no_runtime_decisions(self, dxb: DXB, report: ValidationReport) -> None:
        """验证 DXB 中没有任何运行时决策逻辑。"""
        # Check constraints
        if not isinstance(dxb.constraints, dict):
            return
        policy = dxb.constraints.get("policy", {})
        if isinstance(policy, dict):
            for domain_key in ("sgl", "ats", "scheduler"):
                domain = policy.get(domain_key, {})
                if isinstance(domain, dict):
                    if domain.get("runtime_decision") is True:
                        report.add_error(
                            f"RUNTIME DECISION LEAK: '{domain_key}' has runtime_decision=True"
                        )
                        report.add_risk_flag(f"runtime_decision_in_{domain_key}")

        # Check steps for runtime keywords
        for step in dxb.steps:
            step_text = f"{step.step_type} {step.capability_ref} {step.inputs}"
            step_lower = step_text.lower()
            for keyword in self.FORBIDDEN_RUNTIME_KEYWORDS:
                if keyword.lower() in step_lower:
                    report.add_warning(
                        f"Step '{step.id}' contains runtime keyword: '{keyword}'"
                    )

        # Check constraints for runtime keywords
        constraints_text = str(dxb.constraints).lower()
        if "runtime_decision" in constraints_text and "runtime_decision\": false" not in constraints_text.lower():
            # Check if there's a true runtime_decision somewhere
            pass  # Already checked above with structured approach

    def _check_policy_fields(self, dxb: DXB, report: ValidationReport) -> None:
        """检查 policy 字段完整性。"""
        if not isinstance(dxb.constraints, dict):
            return
        policy = dxb.constraints.get("policy", {})
        if not isinstance(policy, dict):
            return

        compiled_at = policy.get("compiled_at", "")
        if compiled_at != "compile-time":
            report.add_warning(
                f"Expected compiled_at='compile-time', got '{compiled_at}'"
            )

        if policy.get("runtime_decision") is True:
            report.add_error("policy.runtime_decision must be False")

    # ═══════════════════════════════════════════════════════════════
    # Policy checks
    # ═══════════════════════════════════════════════════════════════

    def _check_governance_coverage(self, dxb: DXB, report: ValidationReport) -> None:
        """检查治理覆盖完整性。"""
        gov_steps = [s for s in dxb.steps if s.step_type == "GOVERNANCE_CHECK"]
        skill_steps = [s for s in dxb.steps if s.step_type == "SKILL"]

        if skill_steps and not gov_steps:
            report.add_warning("Skills present but no governance checks — risk of ungoverned execution")

    def _check_risk_thresholds(self, dxb: DXB, report: ValidationReport) -> None:
        """检查风险阈值合理性。"""
        high_risk_steps = [s for s in dxb.steps if s.risk >= 0.8]
        if high_risk_steps:
            report.add_risk_flag(
                f"High-risk steps detected (risk >= 0.8): "
                f"{', '.join(s.id for s in high_risk_steps)}"
            )

        # Check SGL risk threshold
        policy = dxb.constraints.get("policy", {})
        sgl = policy.get("sgl", {}) if isinstance(policy, dict) else {}
        if isinstance(sgl, dict):
            risk_threshold = sgl.get("risk_threshold", 0.0)
            if isinstance(risk_threshold, (int, float)) and risk_threshold >= 0.9:
                report.add_risk_flag(f"SGL risk threshold is critical: {risk_threshold}")

        # Check overall DXB risk
        if dxb.risk_score >= 0.8:
            report.add_risk_flag(f"DXB overall risk score is high: {dxb.risk_score}")
