"""Evolution Gate — 演化建议的四道闸门检查

每道建议必须通过四个检查才能被允许应用:
  1. Health Check     — 系统健康度 >= 0.6
  2. Drift Check      — 无漂移
  3. Rollback Check   — 无活跃回滚
  4. Benchmark Check  — 基准测试（占位，始终通过）

所有检查 deterministic，单点故障不级联崩溃。
"""

from __future__ import annotations

import hashlib
from typing import Any

from governance.evolution.types import (
    EvolutionSuggestion,
    EvolutionVerdict,
    GateCheckResult,
)

# ─── 健康检查阈值 ────────────────────────────────────────────────────────────

_HEALTH_THRESHOLD = 0.60


class EvolutionGate:
    """演化闸门 — 四道检查复合判定。

    Usage:
        gate = EvolutionGate(meta_control_plane=mcp, stability_layer=sl)
        verdicts = gate.check(suggestions)
        for v in verdicts:
            if v.allowed:
                apply_suggestion(...)
    """

    def __init__(
        self,
        meta_control_plane: Any | None = None,
        stability_layer: Any | None = None,
    ):
        self._mcp = meta_control_plane
        self._sl = stability_layer

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def check(
        self, suggestions: list[EvolutionSuggestion],
    ) -> list[EvolutionVerdict]:
        """对每条建议执行四道闸门检查。

        Args:
            suggestions: 演化建议列表

        Returns:
            每条建议对应的 EvolutionVerdict（顺序与输入一致）
        """
        return [
            self._inspect(suggestion, idx)
            for idx, suggestion in enumerate(suggestions)
        ]

    # ═══════════════════════════════════════════════════════════════════
    # 单条建议检查
    # ═══════════════════════════════════════════════════════════════════

    def _inspect(
        self, suggestion: EvolutionSuggestion, idx: int,
    ) -> EvolutionVerdict:
        """对单条建议执行四道检查。"""
        passed: list[GateCheckResult] = []
        failed: list[GateCheckResult] = []

        # Check 1: Health
        health_result = self._check_health()
        (passed if health_result.passed else failed).append(health_result)

        # Check 2: Drift
        drift_result = self._check_drift()
        (passed if drift_result.passed else failed).append(drift_result)

        # Check 3: Rollback
        rollback_result = self._check_rollback()
        (passed if rollback_result.passed else failed).append(rollback_result)

        # Check 4: Benchmark (always passes — placeholder)
        benchmark_result = self._check_benchmark()
        (passed if benchmark_result.passed else failed).append(benchmark_result)

        return EvolutionVerdict(
            suggestion_id=self._suggestion_id(suggestion, idx),
            passed_checks=tuple(passed),
            failed_checks=tuple(failed),
        )

    # ═══════════════════════════════════════════════════════════════════
    # 四项检查
    # ═══════════════════════════════════════════════════════════════════

    def _check_health(self) -> GateCheckResult:
        """Check 1: 系统健康检查。

        依赖 MetaControlPlane（可选）:
          - 优先读取 mcp.system_health_monitor.health_score
          - 回退调用 mcp.process({"health_check": True}, ...)
        """
        if self._mcp is None:
            return GateCheckResult(
                check_name="health",
                passed=True,
                detail="No MetaControlPlane available — health check skipped",
            )

        try:
            health_score = self._mcp.system_health_monitor.health_score
            if isinstance(health_score, float):
                return self._health_result(health_score)
        except (AttributeError, TypeError):
            pass

        try:
            result = self._mcp.process(
                {"health_check": True}, {"adjustments": {}},
            )
            meta = result.get("meta_decision", {})
            health_score = meta.get("health_score", 0.0)
            return self._health_result(health_score)
        except Exception as exc:
            return GateCheckResult(
                check_name="health",
                passed=False,
                detail=f"Health check error: {exc}",
            )

    def _check_drift(self) -> GateCheckResult:
        """Check 2: 漂移检查。

        依赖 StabilityLayer（可选）:
          - 优先检查 sl.drift_detected 属性
          - 回退调用 sl.run(...) 解析
        """
        if self._sl is None:
            return GateCheckResult(
                check_name="drift",
                passed=True,
                detail="No StabilityLayer available — drift check skipped",
            )

        try:
            if hasattr(self._sl, "drift_detected"):
                drift = bool(self._sl.drift_detected)
                return self._drift_result(drift)
        except (AttributeError, TypeError):
            pass

        try:
            if hasattr(self._sl, "run"):
                result = self._sl.run()
                drift_info = result.get("drift", {})
                drift = drift_info.get("drift_detected", False)
                return self._drift_result(bool(drift))
        except Exception as exc:
            return GateCheckResult(
                check_name="drift",
                passed=False,
                detail=f"Drift check error: {exc}",
            )

        return GateCheckResult(
            check_name="drift",
            passed=True,
            detail="Unable to determine drift — assuming no drift",
        )

    def _check_rollback(self) -> GateCheckResult:
        """Check 3: 回滚 + Safety Lock 检查。

          - sl.rollback["triggered"] 活跃 → 阻塞
          - sl.is_locked() 或 sl.lock_active 锁定 → 阻塞
        """
        if self._sl is None:
            return GateCheckResult(
                check_name="rollback",
                passed=True,
                detail="No StabilityLayer available — rollback check skipped",
            )

        # ── Rollback 检查 ──
        rollback_active = False
        rollback_detail = ""
        try:
            if hasattr(self._sl, "rollback"):
                rb = self._sl.rollback
                if isinstance(rb, dict):
                    rollback_active = rb.get("triggered", False)
                    rollback_detail = f"Rollback active: {rb.get('reasons', [])}"
            else:
                result = self._sl.run()
                rb = result.get("rollback", {})
                rollback_active = rb.get("triggered", False)
                rollback_detail = f"Rollback active: {rb.get('reasons', [])}"
        except AttributeError:
            pass
        except Exception as exc:
            return GateCheckResult(
                check_name="rollback",
                passed=False,
                detail=f"Rollback check error: {exc}",
            )

        if rollback_active:
            return GateCheckResult(
                check_name="rollback",
                passed=False,
                detail=rollback_detail or "Rollback is active",
            )

        # ── Safety Lock 检查 ──
        try:
            locked = False
            if hasattr(self._sl, "is_locked") and callable(self._sl.is_locked):
                locked = bool(self._sl.is_locked())
            elif hasattr(self._sl, "_lock_active"):
                locked = bool(self._sl._lock_active)

            if locked:
                return GateCheckResult(
                    check_name="rollback",
                    passed=False,
                    detail="Safety lock is active — rollback check blocked",
                )
        except Exception as exc:
            return GateCheckResult(
                check_name="rollback",
                passed=False,
                detail=f"Safety lock check error: {exc}",
            )

        return GateCheckResult(
            check_name="rollback",
            passed=True,
            detail="No rollback or safety lock active",
        )

    def _check_benchmark(self) -> GateCheckResult:
        """Check 4: 基准检查（占位）。

        实际 benchmark 集成会运行 pytest suite 并验证
        关键指标是否在预期范围内。当前版本始终通过。
        """
        return GateCheckResult(
            check_name="benchmark",
            passed=True,
            detail="Benchmark check: placeholder — always passes",
        )

    # ═══════════════════════════════════════════════════════════════════
    # 内部辅助
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _health_result(health_score: float) -> GateCheckResult:
        passed = health_score >= _HEALTH_THRESHOLD
        return GateCheckResult(
            check_name="health",
            passed=passed,
            detail=f"Health score = {health_score:.4f} "
                   f"(threshold >= {_HEALTH_THRESHOLD}, "
                   f"{'PASS' if passed else 'BLOCKED'})",
        )

    @staticmethod
    def _drift_result(drift_detected: bool) -> GateCheckResult:
        return GateCheckResult(
            check_name="drift",
            passed=not drift_detected,
            detail=(
                "No drift detected"
                if not drift_detected else
                f"Drift detected"
            ),
        )

    @staticmethod
    def _suggestion_id(
        suggestion: EvolutionSuggestion, idx: int,
    ) -> str:
        """为建议生成唯一 ID。"""
        raw = f"{idx}:{suggestion.target}:{suggestion.description}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return f"sug_{idx}_{h}"
