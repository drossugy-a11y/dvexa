"""Assimilation Sandbox — Phase 5

所有 pattern 必须先在 sandbox 中测试，禁止直接注入生产 runtime。

规则:
  - append-only 变更
  - 可回滚
  - 不修改 frozen layer
  - 所有注入必须生成 snapshot
"""

from __future__ import annotations

from typing import Any


class AssimilationSandbox:
    """沙箱注入环境 — 隔离测试模式注入。

    Flow:
        1. inject_pattern(pattern) → 创建沙箱状态
        2. run_regression_suite() → 验证
        3. rollback() 或 commit()
    """

    def __init__(self):
        self._injected_patterns: list[dict] = []
        self._snapshots: list[dict] = []
        self._snapshot_counter = 0
        self._injection_log: list[dict] = []
        self._active_injections: dict[str, dict] = {}

    def inject_pattern(self, pattern: dict) -> dict:
        """在沙箱中注入模式。

        Args:
            pattern: 被批准的模式

        Returns:
            {injection_id, status, snapshot_id}
        """
        name = pattern.get("pattern_name", "unknown")
        injection_id = f"inj_{self._snapshot_counter}_{name}"

        # 创建 pre-injection 快照
        snapshot = self._create_snapshot(f"pre_{injection_id}", pattern)

        injection = {
            "injection_id": injection_id,
            "pattern": pattern,
            "status": "injected",
            "pre_snapshot_id": snapshot["snapshot_id"],
            "timestamp": snapshot["timestamp"],
        }

        self._active_injections[name] = injection
        self._injected_patterns.append(injection)
        self._injection_log.append({
            "action": "inject",
            "injection_id": injection_id,
            "pattern_name": name,
        })

        return {
            "injection_id": injection_id,
            "status": "injected",
            "snapshot_id": snapshot["snapshot_id"],
        }

    def run_regression_suite(self) -> dict:
        """运行回归测试套件。

        模拟执行回归检查:
          1. 检查 frozen layer 未被修改
          2. 检查 pattern 约束未被违反
          3. 检查 governance 一致性

        Returns:
            {passed, total_checks, failed_checks, details[]}
        """
        checks = []
        passed = 0
        failed = 0

        # Check 1: Frozen layer integrity
        frozen_check = self._check_frozen_layer()
        checks.append(frozen_check)
        if frozen_check["passed"]:
            passed += 1
        else:
            failed += 1

        # Check 2: Pattern constraint check
        for inj in self._active_injections.values():
            constraint_check = self._check_pattern_constraints(inj["pattern"])
            checks.append(constraint_check)
            if constraint_check["passed"]:
                passed += 1
            else:
                failed += 1

        # Check 3: Governance consistency
        gov_check = self._check_governance_consistency()
        checks.append(gov_check)
        if gov_check["passed"]:
            passed += 1
        else:
            failed += 1

        return {
            "passed": failed == 0,
            "total_checks": len(checks),
            "passed_count": passed,
            "failed_count": failed,
            "details": checks,
        }

    def rollback(self, injection_id: str | None = None) -> dict:
        """回滚到注入前状态。

        Args:
            injection_id: 要回滚的注入 ID。None = 回滚所有。

        Returns:
            {rolled_back, count}
        """
        if injection_id:
            removed = []
            remaining = []
            for inj in self._injected_patterns:
                if inj["injection_id"] == injection_id:
                    removed.append(inj)
                else:
                    remaining.append(inj)
            self._injected_patterns = remaining

            # 清除活跃注入
            for name, inj in list(self._active_injections.items()):
                if inj["injection_id"] == injection_id:
                    del self._active_injections[name]

            self._injection_log.append({
                "action": "rollback",
                "injection_id": injection_id,
            })

            return {"rolled_back": len(removed) > 0, "count": len(removed)}

        # 回滚全部
        count = len(self._active_injections)
        self._active_injections.clear()
        self._injected_patterns.clear()
        self._injection_log.append({"action": "rollback_all", "count": count})

        return {"rolled_back": True, "count": count}

    def commit(self, injection_id: str) -> dict:
        """提交一个经过验证的注入。"""
        for inj in self._injected_patterns:
            if inj["injection_id"] == injection_id:
                inj["status"] = "committed"
                self._injection_log.append({
                    "action": "commit",
                    "injection_id": injection_id,
                })
                return {"committed": True, "injection_id": injection_id}
        return {"committed": False, "error": "Injection not found"}

    # ═══════════════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════════════

    def _create_snapshot(self, label: str, pattern: dict) -> dict:
        self._snapshot_counter += 1
        sid = f"sandbox_snap_{self._snapshot_counter}"
        from datetime import datetime, timezone
        snapshot = {
            "snapshot_id": sid,
            "label": label,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_injections": list(self._active_injections.keys()),
            "pattern": pattern.get("pattern_name", ""),
        }
        self._snapshots.append(snapshot)
        return snapshot

    def _check_frozen_layer(self) -> dict:
        """验证 frozen layer 未被修改。"""
        frozen_files = ["core/kernel.py", "core/guard.py", "agents/base_agent.py"]
        for inj in self._active_injections.values():
            changes = inj["pattern"].get("required_changes", [])
            for ch in changes:
                for ff in frozen_files:
                    if ff in ch:
                        return {
                            "check": "frozen_layer_integrity",
                            "passed": False,
                            "detail": f"CRITICAL: Pattern touches frozen file: {ff}",
                        }
        return {"check": "frozen_layer_integrity", "passed": True,
                "detail": "Frozen layer intact"}

    def _check_pattern_constraints(self, pattern: dict) -> dict:
        """检查模式约束是否被违反。"""
        violations = []

        # 模式必须有明确的目标层
        rec_layer = pattern.get("recommended_layer", "")
        if not rec_layer:
            violations.append("No recommended_layer specified")

        # 不能提议修改 frozen layer
        changes = pattern.get("required_changes", [])
        for ch in changes:
            if "kernel.py" in ch or "guard.py" in ch:
                violations.append(f"Cannot modify frozen file: {ch}")

        passed = len(violations) == 0
        return {
            "check": f"pattern_constraints:{pattern.get('pattern_name', '')}",
            "passed": passed,
            "detail": "; ".join(violations) if violations else "Constraints satisfied",
        }

    def _check_governance_consistency(self) -> dict:
        """检查治理一致性。"""
        if len(self._active_injections) > 5:
            return {
                "check": "governance_consistency",
                "passed": False,
                "detail": f"Too many active injections ({len(self._active_injections)}), "
                          f"risk of governance bypass",
            }
        return {
            "check": "governance_consistency",
            "passed": True,
            "detail": f"Active injections within governance limits "
                      f"({len(self._active_injections)})",
        }

    # ═══════════════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════════════

    def get_active_injections(self) -> dict[str, dict]:
        return dict(self._active_injections)

    def get_snapshot_count(self) -> int:
        return self._snapshot_counter

    def get_injection_log(self) -> list[dict]:
        return list(self._injection_log)

    def get_snapshots(self) -> list[dict]:
        return list(self._snapshots)
