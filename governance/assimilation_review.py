"""Assimilation Governance Review — Phase 4

对所有提取的模式进行治理兼容性审查。检查复杂度增长、
kernel 边界违规、递归控制风险、运行时稳定性、内存污染风险。

全部 deterministic，不使用 LLM。
"""

from __future__ import annotations

from typing import Any


class AssimilationReview:
    """治理兼容性审查器 — 决定模式是否可安全注入。"""

    # Kernel boundary: 这些目录/文件绝对不能碰
    _KERNEL_BOUNDARY = {
        "core/kernel.py", "core/guard.py", "agents/base_agent.py",
    }

    # Frozen layer: 这些文件不能直接修改
    _FROZEN_LAYER = {
        "core/", "agents/base_agent.py",
    }

    # 允许的扩展层
    _EXTENSIBLE_LAYER = {
        "external/", "capabilities/", "runtime/",
        "evaluation/", "governance/",
    }

    # 高风险关键词: 出现在 required_changes 中时触发警告
    _RISK_KEYWORDS: dict[str, str] = {
        "kernel": "kernel_boundary_violation",
        "executor.py": "execution_flow_change",
        "guard.py": "guard_modification",
        "planner": "planner_override_risk",
        "autonomous": "autonomous_control_risk",
        "concurrent": "concurrent_execution_risk",
        "fork": "process_fork_risk",
        "shell": "shell_execution_risk",
        "write": "filesystem_write_risk",
        "monkey": "monkey_patching_risk",
        "dynamic": "dynamic_code_risk",
        "eval": "code_eval_risk",
        "importlib": "dynamic_import_risk",
    }

    def __init__(self):
        self._reviews: dict[str, dict] = {}

    def review(self, pattern: dict) -> dict:
        """审查单个模式。

        Args:
            pattern: PatternExtractor 输出的单个 pattern dict

        Returns:
            {
                "approved": bool,
                "risk_score": float (0-1, 0=安全),
                "violations": [...],
                "recommended_layer": str,
                "requires_sandbox": bool,
                "pattern_name": str,
            }
        """
        name = pattern.get("pattern_name", "unknown")
        changes = pattern.get("required_changes", [])
        recommendation = pattern.get("adoption_recommendation", "unknown")

        # 拒绝模式直接驳回
        if recommendation == "reject":
            self._reviews[name] = {
                "approved": False,
                "risk_score": 1.0,
                "violations": ["Pattern marked as reject by extractor"],
                "recommended_layer": "NONE",
                "requires_sandbox": False,
                "pattern_name": name,
            }
            return self._reviews[name]

        violations: list[str] = []
        risk_score = 0.0

        # ── Check 1: Complexity Increase ──
        complexity_risk = self._check_complexity(pattern)
        if complexity_risk["violation"]:
            violations.append(complexity_risk["detail"])
        risk_score += complexity_risk["score"]

        # ── Check 2: Governance Violation ──
        gov_risk = self._check_governance(pattern)
        if gov_risk["violation"]:
            violations.extend(gov_risk["details"])
        risk_score += gov_risk["score"]

        # ── Check 3: Kernel Boundary Violation ──
        kernel_risk = self._check_kernel_boundary(pattern)
        if kernel_risk["violation"]:
            violations.extend(kernel_risk["details"])
        risk_score += kernel_risk["score"]

        # ── Check 4: Recursive Control Risk ──
        recursive_risk = self._check_recursive_control(pattern)
        if recursive_risk["violation"]:
            violations.append(recursive_risk["detail"])
        risk_score += recursive_risk["score"]

        # ── Check 5: Runtime Instability Risk ──
        instability_risk = self._check_runtime_instability(pattern)
        if instability_risk["violation"]:
            violations.append(instability_risk["detail"])
        risk_score += instability_risk["score"]

        # ── Check 6: Memory Pollution Risk ──
        memory_risk = self._check_memory_pollution(pattern)
        if memory_risk["violation"]:
            violations.append(memory_risk["detail"])
        risk_score += memory_risk["score"]

        # ── Check 7: Tool Escalation Risk ──
        tool_risk = self._check_tool_escalation(pattern)
        if tool_risk["violation"]:
            violations.append(tool_risk["detail"])
        risk_score += tool_risk["score"]

        # 归一化
        risk_score = min(risk_score / 7.0, 1.0)

        # 判定
        approved = risk_score < 0.5 and len(violations) < 3
        if any(v.startswith("CRITICAL:") for v in violations):
            approved = False

        recommended_layer = self._infer_layer(changes, pattern.get("category", ""))

        self._reviews[name] = {
            "approved": approved,
            "risk_score": round(risk_score, 4),
            "violations": violations,
            "recommended_layer": recommended_layer,
            "requires_sandbox": risk_score > 0.2 or not approved,
            "pattern_name": name,
        }

        return self._reviews[name]

    def review_all(self, patterns: list[dict]) -> dict:
        """批量审查全部模式。

        Returns:
            {
                "total": int,
                "approved_count": int,
                "rejected_count": int,
                "sandbox_count": int,
                "global_violations": [...],
                "results": {...},
            }
        """
        results = {}
        approved_count = 0
        rejected_count = 0
        sandbox_count = 0
        global_violations: list[str] = []

        for p in patterns:
            rv = self.review(p)
            name = rv["pattern_name"]
            results[name] = rv

            if rv["approved"]:
                approved_count += 1
            else:
                rejected_count += 1

            if rv["requires_sandbox"]:
                sandbox_count += 1

            if rv["risk_score"] > 0.7:
                global_violations.append(
                    f"HIGH RISK: {name} (score={rv['risk_score']:.2f})"
                )

        # 检查是否有模式涉及 kernel boundary
        for p in patterns:
            changes = p.get("required_changes", [])
            for ch in changes:
                for kb in self._KERNEL_BOUNDARY:
                    if kb in ch:
                        global_violations.append(
                            f"CRITICAL: Pattern '{p.get('pattern_name')}' "
                            f"touches kernel boundary: {ch}"
                        )

        return {
            "total": len(patterns),
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "sandbox_count": sandbox_count,
            "global_violations": global_violations,
            "results": results,
        }

    # ═══════════════════════════════════════════════════════════════════
    # Individual Checks
    # ═══════════════════════════════════════════════════════════════════

    def _check_complexity(self, pattern: dict) -> dict:
        changes = pattern.get("required_changes", [])
        if len(changes) > 3:
            return {"violation": True, "score": 0.2,
                    "detail": f"Complexity increase: {len(changes)} changes required"}
        if len(changes) > 1:
            return {"violation": True, "score": 0.1,
                    "detail": f"Moderate complexity: {len(changes)} changes"}
        return {"violation": False, "score": 0.0, "detail": ""}

    def _check_governance(self, pattern: dict) -> dict:
        changes = pattern.get("required_changes", [])
        violations: list[str] = []
        score = 0.0

        for ch in changes:
            for kw, vt in self._RISK_KEYWORDS.items():
                if kw in ch.lower():
                    violations.append(f"Governance: {vt} → {ch}")
                    score += 0.1

        return {
            "violation": len(violations) > 0,
            "score": min(score, 0.3),
            "details": violations,
        }

    def _check_kernel_boundary(self, pattern: dict) -> dict:
        changes = pattern.get("required_changes", [])
        violations = []
        score = 0.0

        for ch in changes:
            for kb in self._KERNEL_BOUNDARY:
                if kb in ch:
                    violations.append(f"CRITICAL: Kernel boundary violation → {ch}")
                    score = 1.0

        return {
            "violation": len(violations) > 0,
            "score": score,
            "details": violations,
        }

    def _check_recursive_control(self, pattern: dict) -> dict:
        name = pattern.get("pattern_name", "")
        mechanism = pattern.get("mechanism", "")

        recursive_signals = ["agent can spawn", "self-modify",
                             "recursive", "re-entrant", "nested agent"]
        full = (name + " " + mechanism).lower()

        for sig in recursive_signals:
            if sig in full:
                return {
                    "violation": True,
                    "score": 0.5,
                    "detail": f"Recursive control risk: pattern contains '{sig}'",
                }
        return {"violation": False, "score": 0.0, "detail": ""}

    def _check_runtime_instability(self, pattern: dict) -> dict:
        mechanism = pattern.get("mechanism", "")
        instability_signals = ["replan", "restart", "restart execution",
                               "discard state", "reset context"]

        for sig in instability_signals:
            if sig in mechanism.lower():
                return {
                    "violation": True,
                    "score": 0.2,
                    "detail": f"Runtime instability risk: {sig} in mechanism",
                }
        return {"violation": False, "score": 0.0, "detail": ""}

    def _check_memory_pollution(self, pattern: dict) -> dict:
        name = pattern.get("pattern_name", "")
        mechanism = pattern.get("mechanism", "")

        if "message" in name.lower() or "history" in name.lower():
            if "unbounded" in mechanism.lower() or "append" in name.lower():
                return {
                    "violation": True,
                    "score": 0.15,
                    "detail": "Memory pollution risk: unbounded message growth",
                }
        return {"violation": False, "score": 0.0, "detail": ""}

    def _check_tool_escalation(self, pattern: dict) -> dict:
        name = pattern.get("pattern_name", "")
        mechanism = pattern.get("mechanism", "")

        escalation_signals = ["write", "edit", "shell", "exec",
                              "delete", "rm ", "sudo"]
        full = (name + " " + mechanism).lower()

        for sig in escalation_signals:
            if sig in full:
                return {
                    "violation": True,
                    "score": 0.3,
                    "detail": f"Tool escalation risk: '{sig}' capability detected",
                }
        return {"violation": False, "score": 0.0, "detail": ""}

    def _infer_layer(self, changes: list[str], category: str) -> str:
        if any("core/" in c for c in changes):
            return "core"
        if category in ("planner", "execution"):
            return "capabilities"
        if category in ("memory", "tool"):
            return "runtime"
        if category in ("runtime", "governance"):
            return "evaluation"
        return "external"

    # ═══════════════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════════════

    def get_review(self, pattern_name: str) -> dict | None:
        return self._reviews.get(pattern_name)

    def get_approved_patterns(self) -> list[str]:
        return [n for n, r in self._reviews.items() if r.get("approved")]

    def get_rejected_patterns(self) -> list[str]:
        return [n for n, r in self._reviews.items() if not r.get("approved")]
