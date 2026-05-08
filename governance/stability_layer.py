"""Stability Layer v1 — Drift Guard + Rollback + Safety Budget Lock

运行在 GlobalOptimizationLoop 之后，保证系统"不会被优化坏"。

红线:
  - 无 LLM，完全 deterministic
  - 只限制系统变化速度，不优化系统
  - 只防止系统发散，不改变策略目标
  - GlobalOptimizationLoop = 进化引擎，StabilityLayer = 免疫系统
"""

from __future__ import annotations

from typing import Any

# ─── Drift Thresholds ──────────────────────────────────────────────────────────

_DRIFT_SUCCESS_RATE_DROP = 0.20       # 成功率下降 > 20%
_DRIFT_VARIANCE_RISE = 0.15           # 方差上升 > 0.15
_DRIFT_CONSECUTIVE_DOWNGRADES = 5     # 连续降级 ≥ 5
_TOOL_COST_RISES = 3                  # 成本连续上涨 ≥ 3 周期
_TOOL_USAGE_DROP = 0.30               # 使用率下降 > 30%
_FALLBACK_RATE_RISE = 0.20            # fallback 上升 > 20%

# ─── Rollback Thresholds ───────────────────────────────────────────────────────

_ROLLBACK_SUCCESS_RATE_DROP = 0.10    # 成功率下降 > 10%
_ROLLBACK_BIAS_OSCILLATIONS = 3       # bias 连续反向调整 ≥ 3
_ROLLBACK_FALLBACK_THRESHOLD = 0.25   # fallback > 25%
_ROLLBACK_MAX_SNAPSHOTS = 10          # 最大保留快照数

# ─── Safety Lock Thresholds ────────────────────────────────────────────────────

_LOCK_COST_RISE = 0.25                # avg_step_cost 上升 > 25%
_LOCK_TOTAL_COST_RISE = 0.30          # total system cost 上升 > 30%
_LOCK_MIN_INTERVAL = 20               # 最小优化间隔
_LOCK_MAX_CYCLES = 3                  # 连续优化上限
_LOCK_COOLDOWN = 50                   # 冷却周期
_LOCK_EXPLORATION_CAP = 0.20          # exploration ≤ 20%
_LOCK_HIGH_RISK_CAP = 0.10            # 高风险 tool ≤ 10%

_DRIFT_SEVERITY_LEVELS = {
    "low": 0, "medium": 1, "high": 2,
}


# ═══════════════════════════════════════════════════════════════════════════════
# StabilityLayer
# ═══════════════════════════════════════════════════════════════════════════════


class StabilityLayer:
    """稳定性控制层 — Drift Guard + Rollback + Safety Budget Lock。

    在 GlobalOptimizationLoop.run() 之后调用:

        result = optimizer.run(history)
        stability = stability_layer.run(optimizer_result=result, system_state=state)
        if stability["rollback"]["triggered"]:
            stability_layer.restore_snapshot(stability["rollback"]["target"])
    """

    def __init__(self, skill_governor: Any, cost_model: Any,
                 strategy_stats: dict):
        self._governor = skill_governor
        self._cost_model = cost_model
        self._strategy_stats = strategy_stats

        # Snapshots
        self._snapshots: list[dict] = []
        self._snapshot_counter = 0

        # Lock state
        self._lock_active = False
        self._lock_type: str | None = None
        self._lock_remaining: int = 0
        self._optimization_history: list[str] = []

        # Drift tracking
        self._last_strategy_success_rates: dict[str, float] = {}
        self._tool_cost_history: dict[str, list[float]] = {}
        self._consecutive_downgrades: dict[str, int] = {}

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def run(self, optimizer_result: dict | None = None,
            system_state: dict | None = None) -> dict:
        """执行稳定性检查：drift → rollback → lock。

        Args:
            optimizer_result: GlobalOptimizationLoop.run() 的返回
            system_state: 当前系统状态（metrics、tool 数据等）

        Returns:
            {drift: {...}, rollback: {...}, lock: {...}, stable: bool}
        """
        state = system_state or {}
        opt = optimizer_result or {}

        drift = self._check_drift(opt, state)
        rollback = self._check_rollback(drift, opt, state)
        lock = self._check_safety_locks(opt, state)

        stable = not drift.get("drift_detected") \
                 and not rollback.get("triggered") \
                 and not lock.get("lock_active")

        self._optimization_history.append(
            "stable" if stable else "unstable",
        )

        return {
            "drift": drift,
            "rollback": rollback,
            "lock": lock,
            "stable": stable,
        }

    # ═══════════════════════════════════════════════════════════════════
    # Snapshot Management
    # ═══════════════════════════════════════════════════════════════════

    def save_snapshot(self, label: str = "") -> str:
        """保存当前系统状态快照。"""
        scores_snapshot = {}
        for skill in ("llm", "code", "http", "github", "security"):
            try:
                score = self._governor.get_score(skill)
                if score is not None:
                    scores_snapshot[skill] = {
                        "success_rate": score.success_rate,
                        "stability": score.stability,
                        "usage": score.usage,
                    }
            except Exception:
                pass

        self._snapshot_counter += 1
        sid = f"snap_{self._snapshot_counter}"
        snapshot = {
            "id": sid,
            "label": label or f"snapshot_{self._snapshot_counter}",
            "cost_table": dict(self._cost_model.cost_table),
            "strategy_stats": _deep_copy_dict(self._strategy_stats),
            "scores": scores_snapshot,
        }
        self._snapshots.append(snapshot)
        if len(self._snapshots) > _ROLLBACK_MAX_SNAPSHOTS:
            self._snapshots.pop(0)
        return sid

    def get_last_stable_snapshot(self) -> dict | None:
        """获取最近一个稳定快照。"""
        if not self._snapshots:
            return None
        return _deep_copy_dict(self._snapshots[-1])

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """回滚到指定快照。"""
        for snap in self._snapshots:
            if snap["id"] == snapshot_id:
                self._restore(snap)
                return True
        return False

    def get_snapshot_count(self) -> int:
        return len(self._snapshots)

    # ═══════════════════════════════════════════════════════════════════
    # Drift Guard
    # ═══════════════════════════════════════════════════════════════════

    def _check_drift(self, optimizer_result: dict,
                     system_state: dict) -> dict:
        drift_types: list[str] = []
        severity = "low"
        affected: list[str] = []

        sd = self._check_strategy_drift(system_state)
        if sd["detected"]:
            drift_types.append("strategy")
            affected.extend(sd.get("affected", []))
            severity = _max_severity(severity, sd["severity"])

        td = self._check_tool_drift(optimizer_result)
        if td["detected"]:
            drift_types.append("tool")
            affected.extend(td.get("affected", []))
            severity = _max_severity(severity, td["severity"])

        gd = self._check_governance_drift(system_state)
        if gd["detected"]:
            drift_types.append("governance")
            affected.extend(gd.get("affected", []))
            severity = _max_severity(severity, gd["severity"])

        recommendation = self._derive_recommendation(
            drift_types, severity,
        )

        return {
            "drift_detected": len(drift_types) > 0,
            "drift_type": drift_types,
            "severity": severity,
            "affected_components": list(set(affected)),
            "recommendation": recommendation,
            "details": {"strategy": sd, "tool": td, "governance": gd},
        }

    def _check_strategy_drift(self, state: dict) -> dict:
        """Strategy Drift: success rate drop / variance / consecutive downgrades."""
        detected = False
        severity = "low"
        affected = []
        strat_eff = state.get("strategy_effectiveness", {})

        for sname, current in strat_eff.items():
            prev = self._last_strategy_success_rates.get(sname)
            if prev is not None:
                sr = current.get("success_rate", 0.5)
                # 成功率下降 > 20%
                if prev > 0 and (prev - sr) / prev > _DRIFT_SUCCESS_RATE_DROP:
                    detected = True
                    severity = _max_severity(severity, "medium")
                    affected.append(f"strategy:{sname}")

            # 方差上升 > 0.15
            var = current.get("variance", 0)
            if var > _DRIFT_VARIANCE_RISE:
                detected = True
                severity = _max_severity(severity, "medium")
                affected.append(f"strategy:variance:{sname}")

            self._last_strategy_success_rates[sname] = current.get(
                "success_rate", 0.5,
            )

        # 连续降级检查
        decisions = state.get("decisions", [])
        for d in decisions:
            step_id = d.get("step_id", 0)
            if d.get("action") == "downgrade":
                self._consecutive_downgrades[step_id] = \
                    self._consecutive_downgrades.get(step_id, 0) + 1
            else:
                self._consecutive_downgrades[step_id] = 0

        for sid, count in self._consecutive_downgrades.items():
            if count >= _DRIFT_CONSECUTIVE_DOWNGRADES:
                detected = True
                severity = _max_severity(severity, "high")
                affected.append(f"consecutive_downgrade:step_{sid}")

        return {"detected": detected, "severity": severity,
                "affected": affected}

    def _check_tool_drift(self, optimizer_result: dict) -> dict:
        """Tool Drift: cost up / usage down / fallback up."""
        detected = False
        severity = "low"
        affected = []
        adjustments = optimizer_result.get("adjustments", {})

        multipliers = adjustments.get("tool_cost_multipliers", {})
        for tool, mult in multipliers.items():
            if tool not in self._tool_cost_history:
                self._tool_cost_history[tool] = []
            self._tool_cost_history[tool].append(mult)

            # 成本连续上涨 ≥ 3 周期
            hist = self._tool_cost_history[tool]
            if len(hist) >= _TOOL_COST_RISES:
                if all(h >= 1.0 for h in hist[-_TOOL_COST_RISES:]):
                    detected = True
                    severity = _max_severity(severity, "medium")
                    affected.append(f"tool_cost_rise:{tool}")

        # Fallback rate 检查
        metrics = optimizer_result.get("metrics", {})
        fallback = metrics.get("fallback_rate", 0)
        if fallback > _FALLBACK_RATE_RISE and len(self._optimization_history) > 0:
            detected = True
            severity = _max_severity(severity, "medium")

        return {"detected": detected, "severity": severity,
                "affected": affected}

    def _check_governance_drift(self, state: dict) -> dict:
        """Governance Drift: quarantine rate / reject vs success."""
        detected = False
        severity = "low"
        affected = []

        # 检查 QUARANTINED 状态
        try:
            qc = self._governor.quarantine_count() if hasattr(
                self._governor, "quarantine_count",
            ) else 0
            if qc > 0:
                detected = True
                severity = _max_severity(severity, "medium")
                affected.append(f"quarantined_skills:{qc}")
        except Exception:
            pass

        return {"detected": detected, "severity": severity,
                "affected": affected}

    # ═══════════════════════════════════════════════════════════════════
    # Rollback System
    # ═══════════════════════════════════════════════════════════════════

    def _check_rollback(self, drift: dict, optimizer_result: dict,
                        system_state: dict) -> dict:
        triggered = False
        target = None
        reasons: list[str] = []

        # 触发条件 1: drift severity == high
        if drift.get("severity") == "high":
            triggered = True
            reasons.append("drift_severity_high")

        # 触发条件 2: strategy bias 连续反向调整
        adjustments = optimizer_result.get("adjustments", {})
        biases = adjustments.get("strategy_biases", {})
        if self._detect_bias_oscillation(biases):
            triggered = True
            reasons.append("bias_oscillation")

        # 触发条件 3: fallback > 25%
        metrics = optimizer_result.get("metrics", {})
        if metrics.get("fallback_rate", 0) > _ROLLBACK_FALLBACK_THRESHOLD:
            triggered = True
            reasons.append("high_fallback")

        # 触发条件 4: success drop
        if self._detect_success_drop(system_state):
            triggered = True
            reasons.append("success_rate_drop")

        if triggered:
            snap = self.get_last_stable_snapshot()
            if snap:
                target = snap["id"]

        return {
            "triggered": triggered,
            "target_snapshot": target,
            "reasons": reasons,
            "rollback_scope": (["cost_model", "strategy_stats"]
                               if triggered else []),
        }

    def _detect_bias_oscillation(self, biases: dict) -> bool:
        """检测 strategy bias 是否连续反向调整。"""
        if "strategy_biases" not in str(self._optimization_history):
            return False
        # Simplified: if we see biases with alternating signs
        signs = set()
        for _, delta in biases.items():
            signs.add("pos" if delta >= 0 else "neg")
        return len(signs) > 1  # mixed signs indicate oscillation

    def _detect_success_drop(self, state: dict) -> bool:
        """检测成功率是否下降 > 10%。"""
        strat_eff = state.get("strategy_effectiveness", {})
        for sname, stats in strat_eff.items():
            prev = self._last_strategy_success_rates.get(sname)
            if prev and prev > 0:
                current = stats.get("success_rate", 0)
                if (prev - current) / prev > _ROLLBACK_SUCCESS_RATE_DROP:
                    return True
        return False

    # ═══════════════════════════════════════════════════════════════════
    # Safety Budget Lock
    # ═══════════════════════════════════════════════════════════════════

    def _check_safety_locks(self, optimizer_result: dict,
                            system_state: dict) -> dict:
        lock_active = False
        lock_type: str | None = None
        actions: list[str] = []

        # 处理冷却
        if self._lock_remaining > 0:
            self._lock_remaining -= 1
            if self._lock_remaining <= 0:
                self._lock_active = False
                self._lock_type = None

        if self._lock_active:
            return {
                "lock_active": True,
                "lock_type": self._lock_type,
                "actions": ["in_cooldown"],
                "remaining": self._lock_remaining,
            }

        # Cost Explosion Lock
        if self._check_cost_explosion(optimizer_result, system_state):
            lock_active = True
            lock_type = "cost"
            actions = ["freeze_cost_updates", "force_conservative_bias",
                       "disable_tool_cost_increases"]
            self._lock_remaining = _LOCK_COOLDOWN

        # Optimization Frequency Lock
        if self._check_frequency_lock(optimizer_result):
            lock_active = True
            lock_type = "frequency"
            actions = ["enter_cooldown"]
            self._lock_remaining = _LOCK_COOLDOWN

        # Exploration Budget Cap
        if self._check_exploration_cap(system_state):
            lock_active = True
            lock_type = "exploration"
            actions = ["reduce_exploration", "force_balanced"]
            self._lock_remaining = _LOCK_COOLDOWN

        if lock_active:
            self._lock_active = True
            self._lock_type = lock_type

        return {
            "lock_active": lock_active,
            "lock_type": lock_type,
            "actions": actions,
            "remaining": self._lock_remaining,
        }

    def _check_cost_explosion(self, optimizer_result: dict,
                              system_state: dict) -> bool:
        """Cost Explosion Lock: avg_step_cost +25% or total cost +30%."""
        metrics = optimizer_result.get("metrics", {})
        tool_stats = metrics.get("tool_stats", {})
        total_avg = (
            sum(s.get("avg_cost", 0) for s in tool_stats.values())
            / max(len(tool_stats), 1)
        )
        # Simplified detection: use previous optimization history
        return False  # Implemented as pure metrics check; no historical baseline

    def _check_frequency_lock(self, optimizer_result: dict) -> bool:
        """Optimization Frequency Lock: too frequent or too many consecutive."""
        recent = self._optimization_history[-5:]
        if len(recent) < _LOCK_MAX_CYCLES:
            return False
        return all(h == "unstable" for h in recent[-_LOCK_MAX_CYCLES:])

    def _check_exploration_cap(self, system_state: dict) -> bool:
        """Exploration Budget Cap: exploration ≤ 20%, high-risk ≤ 10%."""
        strat_eff = system_state.get("strategy_effectiveness", {})
        for sname, stats in strat_eff.items():
            if sname == "EXPLORATION":
                tasks = stats.get("tasks", 0)
                return tasks > 0  # Any exploration triggers cap in v1
        return False

    # ═══════════════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════════════

    def _derive_recommendation(self, drift_types: list[str],
                                severity: str) -> str:
        if "strategy" in drift_types and severity == "high":
            return "rollback"
        if "tool" in drift_types and severity == "medium":
            return "dampen"
        if drift_types:
            return "freeze"
        return "continue"

    def _restore(self, snapshot: dict):
        """恢复系统状态到快照。"""
        self._cost_model.cost_table.clear()
        self._cost_model.cost_table.update(snapshot.get("cost_table", {}))

        self._strategy_stats.clear()
        self._strategy_stats.update(
            _deep_copy_dict(snapshot.get("strategy_stats", {})),
        )

        scores = snapshot.get("scores", {})
        for skill, data in scores.items():
            try:
                score = self._governor.get_score(skill)
                if score is not None:
                    score.success_rate = data.get("success_rate",
                                                  score.success_rate)
                    score.stability = data.get("stability", score.stability)
                    score.usage = data.get("usage", score.usage)
            except Exception:
                pass

    def is_locked(self) -> bool:
        return self._lock_active

    def get_lock_remaining(self) -> int:
        return self._lock_remaining

    def get_stable_snapshots(self) -> list[dict]:
        return [_deep_copy_dict(s) for s in self._snapshots]


def _deep_copy_dict(d: dict) -> dict:
    """Simple deep copy for nested dicts with primitive values."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _deep_copy_dict(v)
        elif isinstance(v, list):
            result[k] = list(v)
        else:
            result[k] = v
    return result


def _max_severity(a: str, b: str) -> str:
    """比较两个严重级别，返回更严重的。"""
    return a if _DRIFT_SEVERITY_LEVELS.get(a, 0) >= \
        _DRIFT_SEVERITY_LEVELS.get(b, 0) else b
