"""Governance Feedback Engine v1 — Closed-Loop Learning Layer

后执行学习层：在每次任务完成后更新治理参数，使 DVexa 从静态决策
系统进化为自适应治理系统。

红线:
  - 完全确定性（无 LLM）
  - 不修改执行路径
  - 不修改当前任务结果
  - 仅副作用（side-effect only）
  - 日志追加（append-only）
"""

from __future__ import annotations

from typing import Any


# ─── 默认参数 ──────────────────────────────────────────────────────────────

_DEFAULT_ALPHA = 0.1      # 成功奖励系数
_DEFAULT_BETA = 0.15      # 失败惩罚系数
_DEFAULT_FAIL_THRESHOLD = 3   # 重复失败阈值（触发偏好下调）
_DEFAULT_SUCCESS_THRESHOLD = 5  # 重复成功阈值（触发偏好上调）
_DRIFT_WINDOW = 20        # ATS 漂移检测滑动窗口大小


# ═══════════════════════════════════════════════════════════════════════════
# GovernanceFeedbackEngine
# ═══════════════════════════════════════════════════════════════════════════


class GovernanceFeedbackEngine:
    """治理反馈引擎 — 闭环学习层。

    在每次任务执行后调用 record_execution()，自动更新：
      - Skill 评分（通过 SkillGovernor.record_call）
      - 工具偏好权重（软适应，非硬阻断）
      - 策略性能统计
      - ATS 阈值漂移信号

    Usage:
        engine = GovernanceFeedbackEngine(skill_governor=governor,
                                          strategy_stats=strategy_stats)
        engine.record_execution(execution_trace, outcome)
    """

    def __init__(
        self,
        skill_governor: Any = None,
        tool_policy: Any = None,
        strategy_stats: dict[str, dict[str, float | int]] | None = None,
        *,
        alpha: float = _DEFAULT_ALPHA,
        beta: float = _DEFAULT_BETA,
    ):
        self._governor = skill_governor
        self._tool_policy = tool_policy
        self._strategy_stats = strategy_stats if strategy_stats is not None else {}

        # ── 学习参数 ────────────────────────────────────────────────────
        self.alpha = alpha
        self.beta = beta

        # ── 软偏好权重（独立于 ToolPolicy 的二进制 allow/deny） ──────
        self._preferences: dict[str, float] = {}

        # ── 最近结果环形缓冲区（用于重复检测） ────────────────────────
        self._recent_outcomes: dict[str, list[bool]] = {}

        # ── ATS 漂移信号 ──────────────────────────────────────────────
        self._ats_drift_signals: list[dict] = []

        # ── 追加式历史日志 ────────────────────────────────────────────
        self._history: list[dict] = []

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def record_execution(
        self,
        execution_trace: dict,
        outcome: dict,
    ) -> dict | None:
        """记录一次任务执行并更新治理参数。

        Args:
            execution_trace: {
                "task": "...",
                "strategy_used": "...",
                "steps": [
                    {"step_id": 1, "tool": "...", "action": "...",
                     "success": bool, "latency": float},
                ]
            }
            outcome: {
                "status": "success" | "fail",
                "error_type": "...",
                "total_latency": float,
            }

        Returns:
            None（默认），或调试快照（debug=True 时）。
        """
        trace_id = len(self._history)
        log_entry: dict[str, Any] = {
            "trace_id": trace_id,
            "trace": execution_trace,
            "outcome": outcome,
            "updates": {},
        }

        steps = execution_trace.get("steps", [])
        strategy_used = execution_trace.get("strategy_used", "")

        for step in steps:
            step_id = step.get("step_id", 0)
            tool_name = step.get("tool", "")
            action = step.get("action", "")
            success = step.get("success", True)
            latency = step.get("latency", 0.0)

            if not tool_name:
                continue

            # ── 1. SkillScore Update ──────────────────────────────────
            self._update_skill_score(tool_name, step_id, success, latency)

            # ── 2. Tool Preference Adaptation ─────────────────────────
            pref_delta = self._adapt_tool_preference(tool_name, success)
            log_entry["updates"].setdefault("preferences", {})[tool_name] = {
                "delta": pref_delta,
                "new_value": self._preferences.get(tool_name, 0.0),
            }

        # ── 3. Strategy Statistics Update ─────────────────────────────
        status = outcome.get("status", "fail")
        self._update_strategy_stats(strategy_used, status)

        # ── 4. ATS Drift Signal ───────────────────────────────────────
        drift = self._detect_ats_drift(steps, outcome)
        if drift:
            self._ats_drift_signals.append(drift)
            log_entry["updates"]["ats_drift"] = drift

        # ── 追加式日志 ───────────────────────────────────────────────
        log_entry["updates"]["strategy_stats"] = dict(
            self._strategy_stats.get(strategy_used, {})
        )
        self._history.append(log_entry)

        return None

    # ═══════════════════════════════════════════════════════════════════
    # Query API
    # ═══════════════════════════════════════════════════════════════════

    def get_preference(self, tool_name: str) -> float:
        """获取工具的软偏好权重 [0.0, 1.0]。"""
        return self._preferences.get(tool_name, 0.5)

    def get_strategy_stats(self, strategy: str = "") -> dict:
        """获取策略性能统计。"""
        if strategy:
            return dict(self._strategy_stats.get(strategy, {}))
        return {k: dict(v) for k, v in self._strategy_stats.items()}

    def get_ats_drift_signals(self) -> list[dict]:
        """获取 ATS 漂移信号列表。"""
        return list(self._ats_drift_signals)

    def get_history(self) -> list[dict]:
        """获取完整执行历史（只读）。"""
        return list(self._history)

    def get_debug_snapshot(self) -> dict:
        """获取当前治理学习快照。"""
        return {
            "preferences": dict(self._preferences),
            "strategy_stats": {k: dict(v)
                               for k, v in self._strategy_stats.items()},
            "ats_drift_signals": list(self._ats_drift_signals),
            "total_executions": len(self._history),
        }

    # ═══════════════════════════════════════════════════════════════════
    # Internal: SkillScore Update
    # ═══════════════════════════════════════════════════════════════════

    def _update_skill_score(
        self,
        tool_name: str,
        step_id: int,
        success: bool,
        latency: float,
    ) -> None:
        """通过 SkillGovernor 更新评分。"""
        if not self._governor:
            return
        self._governor.record_call(
            name=tool_name,
            success=success,
            latency=latency,
            error="" if success else f"feedback:step_{step_id}",
        )

    # ═══════════════════════════════════════════════════════════════════
    # Internal: Tool Preference Adaptation (soft)
    # ═══════════════════════════════════════════════════════════════════

    def _adapt_tool_preference(self, tool_name: str, success: bool) -> float:
        """调整工具偏好权重（软适应）。

        策略:
          - 连续 N 次成功 → 偏好 +delta
          - 连续 N 次失败 → 偏好 -delta
          - 结果在 [0.05, 0.95] 范围内

        Returns:
            delta 值（正 = 上调，负 = 下调）
        """
        if tool_name not in self._recent_outcomes:
            self._recent_outcomes[tool_name] = []

        # 维护滑动窗口（仅保留最近的成功/失败计数所需的最少信息）
        outcomes = self._recent_outcomes[tool_name]
        outcomes.append(success)
        if len(outcomes) > _DRIFT_WINDOW:
            outcomes.pop(0)

        # 当前偏好（默认 0.5）
        pref = self._preferences.get(tool_name, 0.5)
        delta = 0.0

        # 检查连续成功
        consecutive_success = 0
        for s in reversed(outcomes):
            if s:
                consecutive_success += 1
            else:
                break
        if consecutive_success >= _DEFAULT_SUCCESS_THRESHOLD:
            delta += self.alpha

        # 检查连续失败
        consecutive_fail = 0
        for s in reversed(outcomes):
            if not s:
                consecutive_fail += 1
            else:
                break
        if consecutive_fail >= _DEFAULT_FAIL_THRESHOLD:
            delta -= self.beta

        if delta != 0.0:
            pref = max(0.05, min(0.95, pref + delta))
            self._preferences[tool_name] = pref

        return delta

    # ═══════════════════════════════════════════════════════════════════
    # Internal: Strategy Statistics
    # ═══════════════════════════════════════════════════════════════════

    def _update_strategy_stats(
        self,
        strategy: str,
        status: str,
    ) -> None:
        """更新策略性能计数器。"""
        if not strategy:
            return

        if strategy not in self._strategy_stats:
            self._strategy_stats[strategy] = {
                "success": 0,
                "fail": 0,
                "total": 0,
                "success_rate": 0.0,
            }

        stats = self._strategy_stats[strategy]
        if status == "success":
            stats["success"] += 1
        else:
            stats["fail"] += 1
        stats["total"] += 1
        stats["success_rate"] = (
            stats["success"] / stats["total"] if stats["total"] > 0 else 0.0
        )

    # ═══════════════════════════════════════════════════════════════════
    # Internal: ATS Drift Detection
    # ═══════════════════════════════════════════════════════════════════

    def _detect_ats_drift(
        self,
        steps: list[dict],
        outcome: dict,
    ) -> dict | None:
        """检测 ATS 阈值漂移信号。

        条件：
          - 整体任务失败
          - 且大部分步骤 marked as "success"（即 ATS 未拦截）
        表示 ATS 可能过于宽松，阈值需要校准。

        Returns:
            漂移信号 dict 或 None
        """
        status = outcome.get("status", "")
        if status != "fail":
            return None

        if not steps:
            return None

        # ATS-approved 步骤中执行失败的比例
        # 所有 steps 都已通过治理检查（即被 ATS 批准执行）
        total_approved = len(steps)
        fail_count = sum(1 for s in steps if not s.get("success", True))
        fail_rate = fail_count / total_approved if total_approved > 0 else 0.0

        if fail_rate > 0.3 and total_approved >= 3:
            return {
                "type": "ats_threshold_drift",
                "approved_steps": total_approved,
                "fail_rate": round(fail_rate, 3),
                "signal": "ATS 阈值可能过于宽松，建议校准",
            }

        return None
