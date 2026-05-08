"""Meta Control Plane v3 — System Evolution Controller

运行在 GlobalOptimizationLoop 之上，StabilityLayer 之下。
控制"优化是否允许发生"，不是优化逻辑本身。

v3 之后 DVexa 变为：
  v2 = "会优化自己的系统"
  v3 = "知道什么时候不能优化自己的系统"

红线:
  - 全部 deterministic（无 LLM）
  - 不影响任务执行逻辑
  - 不改变 planner 输出
  - 不绕过 decision kernel
  - 只能控制"优化是否发生"和"优化幅度"
"""

from __future__ import annotations

from typing import Any

# ─── Health Monitor Thresholds ─────────────────────────────────────────────────

_HEALTH_SUCCESS_RATE_WEIGHT = 0.40
_HEALTH_FALLBACK_RATE_WEIGHT = 0.20
_HEALTH_COST_STABILITY_WEIGHT = 0.20
_HEALTH_STRATEGY_VARIANCE_WEIGHT = 0.20

_HEALTH_STABLE_THRESHOLD = 0.80
_HEALTH_DEGRADED_THRESHOLD = 0.60

# ─── Permission Engine Thresholds ──────────────────────────────────────────────

_PERMISSION_ROLLBACK_RATE_FREEZE = 0.20
_PERMISSION_SUCCESS_DROP_FREEZE = 0.30
_PERMISSION_SUCCESS_DROP_LIMITED = 0.10
_PERMISSION_MODE_TO_VALUE = {"FULL": 2, "LIMITED": 1, "FROZEN": 0}

# ─── Optimization Gate Thresholds ──────────────────────────────────────────────

_GATE_MAX_RECENT_OPTIMIZATIONS = 3
_GATE_COOLDOWN_TASKS = 50

# ─── Evolution Clamp Thresholds ────────────────────────────────────────────────

_CLAMP_COST_MODEL_MAX_CHANGE = 0.20
_CLAMP_STRATEGY_BIAS_MAX_CHANGE = 0.10
_CLAMP_TOOL_WEIGHT_MAX_CHANGE = 0.15
_CLAMP_SKILL_SCORE_MAX_CHANGE = 0.10

# ─── Snapshot Manager ──────────────────────────────────────────────────────────

_SNAPSHOT_MAX_COUNT = 10


# ═══════════════════════════════════════════════════════════════════════════════
# SystemHealthMonitor
# ═══════════════════════════════════════════════════════════════════════════════


class SystemHealthMonitor:
    """系统健康监控器 — 综合打分系统健康度。

    计算权重:
        success_rate        × 0.40
        (1 - fallback_rate) × 0.20
        cost_stability      × 0.20
        (1 - strategy_var)  × 0.20
    """

    def assess(self, system_state: dict) -> dict:
        """评估系统健康度。

        Args:
            system_state: 包含 memory_stats, strategy_stats,
                          cost_model, fallback_rate 等

        Returns:
            {health_score, status, signals[]}
        """
        metrics = self._extract_metrics(system_state)
        score = self._compute_score(metrics)
        status = self._classify(score)
        signals = self._derive_signals(metrics, score)

        return {
            "health_score": round(score, 4),
            "status": status,
            "signals": signals,
        }

    def _extract_metrics(self, state: dict) -> dict:
        strategy_stats = state.get("strategy_stats", {})
        strategy_eff = state.get("strategy_effectiveness", {})

        success_rates = []
        variances = []
        for v in strategy_eff.values():
            if isinstance(v, dict):
                success_rates.append(v.get("success_rate", 0.5))
                variances.append(v.get("variance", 0.0))

        avg_success = (
            sum(success_rates) / len(success_rates)
        ) if success_rates else 0.5
        avg_variance = (
            sum(variances) / len(variances)
        ) if variances else 0.0

        fallback = state.get("fallback_rate",
                             state.get("metrics", {}).get("fallback_rate", 0.0))

        cost_stability = state.get("cost_stability", 1.0)

        return {
            "success_rate": round(avg_success, 4),
            "fallback_rate": round(float(fallback), 4),
            "cost_stability": round(float(cost_stability), 4),
            "strategy_variance": round(avg_variance, 4),
        }

    def _compute_score(self, m: dict) -> float:
        return (
            m["success_rate"] * _HEALTH_SUCCESS_RATE_WEIGHT
            + (1.0 - min(m["fallback_rate"], 1.0)) * _HEALTH_FALLBACK_RATE_WEIGHT
            + m["cost_stability"] * _HEALTH_COST_STABILITY_WEIGHT
            + (1.0 - min(m["strategy_variance"], 1.0)) * _HEALTH_STRATEGY_VARIANCE_WEIGHT
        )

    def _classify(self, score: float) -> str:
        if score >= _HEALTH_STABLE_THRESHOLD:
            return "STABLE"
        if score >= _HEALTH_DEGRADED_THRESHOLD:
            return "DEGRADED"
        return "UNSTABLE"

    def _derive_signals(self, m: dict, score: float) -> list[str]:
        signals = []
        if m["success_rate"] < 0.5:
            signals.append("low_success_rate")
        if m["fallback_rate"] > 0.2:
            signals.append("high_fallback")
        if m["cost_stability"] < 0.5:
            signals.append("cost_instability")
        if m["strategy_variance"] > 0.15:
            signals.append("high_variance")
        if not signals:
            signals.append("nominal")
        return signals


# ═══════════════════════════════════════════════════════════════════════════════
# EvolutionPermissionEngine
# ═══════════════════════════════════════════════════════════════════════════════


class EvolutionPermissionEngine:
    """进化许可引擎 — 决定系统是否可以进化及幅度。"""

    def evaluate(self, health_info: dict, system_state: dict) -> dict:
        """评估进化许可级别。

        Args:
            health_info: SystemHealthMonitor.assess() 的输出
            system_state: 完整系统状态

        Returns:
            {allowed, reason, mode}
        """
        health_score = health_info["health_score"]
        drift = system_state.get("drift", {})
        drift_detected = drift.get("drift_detected", False)
        drift_severity = drift.get("severity", "low")

        rollback = system_state.get("rollback", {})
        rollback_rate = system_state.get("rollback_rate", 0.0)

        strategy_eff = system_state.get("strategy_effectiveness", {})
        success_drop = self._max_success_drop(strategy_eff)

        # Rule 1: drift == HIGH → FROZEN
        if drift_detected and drift_severity == "high":
            return {
                "allowed": False,
                "reason": f"Drift detected (severity={drift_severity})",
                "mode": "FROZEN",
            }

        # Rule 2: rollback_rate > 20% → FROZEN
        if rollback_rate > _PERMISSION_ROLLBACK_RATE_FREEZE:
            return {
                "allowed": False,
                "reason": f"Rollback rate > 20% ({rollback_rate:.2%})",
                "mode": "FROZEN",
            }

        # Rule 3: success_rate drop > 30% → FROZEN
        if success_drop > _PERMISSION_SUCCESS_DROP_FREEZE:
            return {
                "allowed": False,
                "reason": f"Success rate dropped > 30% ({success_drop:.2%})",
                "mode": "FROZEN",
            }

        # Rule 4: success_rate drop > 10% → LIMITED
        if success_drop > _PERMISSION_SUCCESS_DROP_LIMITED:
            return {
                "allowed": True,
                "reason": f"Success rate dropped > 10% ({success_drop:.2%})",
                "mode": "LIMITED",
            }

        # Rule 5: health < 0.6 → LIMITED
        if health_score < _HEALTH_DEGRADED_THRESHOLD:
            return {
                "allowed": True,
                "reason": f"Health score < 0.6 ({health_score:.4f})",
                "mode": "LIMITED",
            }

        # Default: system stable → FULL
        return {
            "allowed": True,
            "reason": "System stable",
            "mode": "FULL",
        }

    def _max_success_drop(self, strategy_eff: dict) -> float:
        """计算各策略中最大的成功率下降幅度。"""
        max_drop = 0.0
        for sname, stats in strategy_eff.items():
            if isinstance(stats, dict):
                prev = stats.get("_previous_rate", stats.get("success_rate", 0.5))
                current = stats.get("success_rate", 0.5)
                if prev > 0:
                    drop = (prev - current) / prev
                    if drop > max_drop:
                        max_drop = drop
        return max_drop


# ═══════════════════════════════════════════════════════════════════════════════
# OptimizationGate
# ═══════════════════════════════════════════════════════════════════════════════


class OptimizationGate:
    """优化闸门 — 控制 GlobalOptimizationLoop 是否允许运行。"""

    def __init__(self):
        self._recent_optimizations: list[int] = []

    def check(self, health_info: dict, permission: dict,
              drift_detected: bool = False) -> dict:
        """检查是否允许优化。

        Args:
            health_info: SystemHealthMonitor.assess() 的输出
            permission: EvolutionPermissionEngine.evaluate() 的输出
            drift_detected: 是否有漂移

        Returns:
            {can_optimize, cooldown_tasks, reason}
        """
        health_score = health_info["health_score"]
        reasons = []

        # Rule 1: health < 0.6 → block
        if health_score < _HEALTH_DEGRADED_THRESHOLD:
            return {
                "can_optimize": False,
                "cooldown_tasks": _GATE_COOLDOWN_TASKS,
                "reason": f"Health score too low ({health_score:.4f})",
            }

        # Rule 2: drift detected → block
        if drift_detected:
            return {
                "can_optimize": False,
                "cooldown_tasks": _GATE_COOLDOWN_TASKS,
                "reason": "Drift detected",
            }

        # Rule 3: mode is FROZEN → block
        if permission.get("mode") == "FROZEN":
            return {
                "can_optimize": False,
                "cooldown_tasks": _GATE_COOLDOWN_TASKS,
                "reason": "Evolution permission is FROZEN",
            }

        # Rule 4: too many recent optimizations → cooldown
        if self._in_cooldown():
            remaining = self._cooldown_remaining()
            return {
                "can_optimize": False,
                "cooldown_tasks": remaining,
                "reason": f"Cooldown active ({remaining} tasks remaining)",
            }

        return {
            "can_optimize": True,
            "cooldown_tasks": 0,
            "reason": "Gate open",
        }

    def record_optimization(self, task_count: int):
        """记录一次优化发生。"""
        self._recent_optimizations.append(task_count)
        if len(self._recent_optimizations) > 20:
            self._recent_optimizations = self._recent_optimizations[-20:]

    def _in_cooldown(self) -> bool:
        """最近 50 轮内优化次数是否 > 3。"""
        if len(self._recent_optimizations) <= _GATE_MAX_RECENT_OPTIMIZATIONS:
            return False
        return True

    def _cooldown_remaining(self) -> int:
        """距上次优化轮数。"""
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# EvolutionClamp
# ═══════════════════════════════════════════════════════════════════════════════


class EvolutionClamp:
    """进化幅度限制器 — 限制每次优化的变化幅度。"""

    def clamp(self, proposed_adjustments: dict,
              previous_adjustments: dict | None = None) -> dict:
        """钳制优化变化幅度。

        Args:
            proposed_adjustments: GlobalOptimizationLoop 提出的调整
            previous_adjustments: 上一次实际应用的调整（用于对比）

        Returns:
            {clamped, adjusted_changes, violations[]}
        """
        prev = previous_adjustments or {}
        clamped = False
        violations: list[str] = []
        adjusted = {"tool_cost_multipliers": {}, "strategy_biases": {},
                    "skill_score_updates": {}}

        # ── Clamp: tool_cost_multipliers ──
        proposed_cost = proposed_adjustments.get("tool_cost_multipliers", {})
        prev_cost = prev.get("tool_cost_multipliers", {})
        for tool, mult in proposed_cost.items():
            old = prev_cost.get(tool, 1.0)
            change = abs(mult - old)
            if change > _CLAMP_COST_MODEL_MAX_CHANGE:
                clamped = True
                violations.append(f"cost:{tool} change {change:.3f} > {_CLAMP_COST_MODEL_MAX_CHANGE}")
                direction = 1 if mult > old else -1
                adjusted["tool_cost_multipliers"][tool] = round(
                    old + direction * _CLAMP_COST_MODEL_MAX_CHANGE, 4,
                )
            else:
                adjusted["tool_cost_multipliers"][tool] = mult

        # ── Clamp: strategy_biases ──
        proposed_biases = proposed_adjustments.get("strategy_biases", {})
        prev_biases = prev.get("strategy_biases", {})
        for sname, bias in proposed_biases.items():
            old = prev_biases.get(sname, 0.0)
            change = abs(bias - old)
            if change > _CLAMP_STRATEGY_BIAS_MAX_CHANGE:
                clamped = True
                violations.append(f"strategy_bias:{sname} change {change:.3f} > {_CLAMP_STRATEGY_BIAS_MAX_CHANGE}")
                direction = 1 if bias > old else -1
                adjusted["strategy_biases"][sname] = round(
                    old + direction * _CLAMP_STRATEGY_BIAS_MAX_CHANGE, 4,
                )
            else:
                adjusted["strategy_biases"][sname] = bias

        # ── Clamp: tool_weight (from prune_suggestions or similar) ──
        proposed_weights = proposed_adjustments.get("tool_weight_updates", {})
        prev_weights = prev.get("tool_weight_updates", {})
        for tool, weight in proposed_weights.items():
            old = prev_weights.get(tool, weight)
            change = abs(weight - old)
            if change > _CLAMP_TOOL_WEIGHT_MAX_CHANGE:
                clamped = True
                violations.append(f"tool_weight:{tool} change {change:.3f} > {_CLAMP_TOOL_WEIGHT_MAX_CHANGE}")
                direction = 1 if weight > old else -1
                adjusted["tool_weight_updates"] = adjusted.get("tool_weight_updates", {})
                adjusted["tool_weight_updates"][tool] = round(
                    old + direction * _CLAMP_TOOL_WEIGHT_MAX_CHANGE, 4,
                )
            else:
                adjusted["tool_weight_updates"] = adjusted.get("tool_weight_updates", {})
                adjusted["tool_weight_updates"][tool] = weight

        # ── Clamp: skill_score ──
        proposed_scores = proposed_adjustments.get("skill_score_updates", {})
        prev_scores = prev.get("skill_score_updates", {})
        for skill, delta in proposed_scores.items():
            change = abs(delta)
            if change > _CLAMP_SKILL_SCORE_MAX_CHANGE:
                clamped = True
                violations.append(f"skill_score:{skill} change {change:.3f} > {_CLAMP_SKILL_SCORE_MAX_CHANGE}")
                direction = 1 if delta > 0 else -1
                adjusted["skill_score_updates"][skill] = round(
                    direction * _CLAMP_SKILL_SCORE_MAX_CHANGE, 4,
                )
            else:
                adjusted["skill_score_updates"][skill] = delta

        return {
            "clamped": clamped,
            "adjusted_changes": adjusted,
            "violations": violations,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SnapshotManager
# ═══════════════════════════════════════════════════════════════════════════════


class SnapshotManager:
    """快照与版本管理器 — 管理系统进化历史。

    与 StabilityLayer 的快照系统独立：
      - StabilityLayer → 系统状态快照（cost_table, strategy_stats）
      - SnapshotManager → 进化决策快照（何时/为什么优化被允许/阻止）
    """

    def __init__(self):
        self._snapshots: list[dict] = []
        self._counter = 0
        self._last_stable_index: int | None = None

    def create_snapshot(self, system_state: dict, reason: str = "") -> str:
        """创建进化快照。

        Args:
            system_state: 系统状态摘要
            reason: 快照原因

        Returns:
            snapshot_id
        """
        self._counter += 1
        sid = f"meta_snap_{self._counter}"
        snapshot = {
            "snapshot_id": sid,
            "timestamp": _now_iso(),
            "system_state": _deep_copy_dict(system_state),
            "reason": reason or f"snapshot_{self._counter}",
        }
        self._snapshots.append(snapshot)
        if len(self._snapshots) > _SNAPSHOT_MAX_COUNT:
            removed = self._snapshots.pop(0)
            if self._last_stable_index is not None:
                self._last_stable_index = max(0, self._last_stable_index - 1)

        # 标记为稳定快照（如果系统稳定）
        if system_state.get("stable", True):
            self._last_stable_index = len(self._snapshots) - 1

        return sid

    def get_last_stable_snapshot(self) -> dict | None:
        """获取最近一个稳定快照。"""
        if self._last_stable_index is not None and self._snapshots:
            return _deep_copy_dict(self._snapshots[self._last_stable_index])
        # 回退：最后一个快照
        if self._snapshots:
            return _deep_copy_dict(self._snapshots[-1])
        return None

    def rollback_to(self, snapshot_id: str) -> dict | None:
        """回滚到指定快照。

        Returns:
            快照内容，或 None（如果未找到）
        """
        for snap in self._snapshots:
            if snap["snapshot_id"] == snapshot_id:
                return _deep_copy_dict(snap)
        return None

    def get_snapshot_count(self) -> int:
        return len(self._snapshots)

    def get_all_snapshots(self) -> list[dict]:
        return [_deep_copy_dict(s) for s in self._snapshots]


# ═══════════════════════════════════════════════════════════════════════════════
# MetaControlPlane — 主控制入口
# ═══════════════════════════════════════════════════════════════════════════════


class MetaControlPlane:
    """元控制层 v3 — 系统进化控制器。

    Usage:
        mcp = MetaControlPlane()
        result = mcp.process(system_state, optimization_request)

        if not result["meta_decision"]["allowed"]:
            skip optimization
    """

    def __init__(self):
        self._health_monitor = SystemHealthMonitor()
        self._permission_engine = EvolutionPermissionEngine()
        self._gate = OptimizationGate()
        self._clamp = EvolutionClamp()
        self._snapshot_manager = SnapshotManager()

        self._last_adjustments: dict = {}
        self._process_count = 0

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def process(self, system_state: dict,
                optimization_request: dict | None = None) -> dict:
        """主控制入口 — 5 步流水线。

        Step 1: Health Check
        Step 2: Permission Check
        Step 3: Optimization Gate
        Step 4: Clamp Changes
        Step 5: Snapshot Decision

        Args:
            system_state: 当前系统状态
            optimization_request: 待审批的优化请求

        Returns:
            {meta_decision, clamped_changes, snapshot_action, reason}
        """
        self._process_count += 1
        opt = optimization_request or {}

        # Step 1: Health Check
        health = self._health_monitor.assess(system_state)

        # Step 2: Permission Check
        permission = self._permission_engine.evaluate(health, system_state)

        # Step 3: Optimization Gate
        drift = system_state.get("drift", {})
        gate = self._gate.check(
            health, permission,
            drift_detected=drift.get("drift_detected", False),
        )

        # Step 4: Clamp Changes
        proposed = opt.get("adjustments", {})
        clamped_result = self._clamp.clamp(proposed, self._last_adjustments)

        # Step 5: Snapshot Decision
        snapshot_action = "NONE"
        if permission["mode"] == "FROZEN":
            snapshot_action = "ROLLBACK"
        elif gate["can_optimize"] and not clamped_result["clamped"]:
            snapshot_action = "CREATE"
        elif clamped_result["clamped"]:
            snapshot_action = "CREATE"

        if snapshot_action == "CREATE":
            self._snapshot_manager.create_snapshot(system_state, permission["reason"])

        # Determine overall allowed
        mode = permission["mode"]
        if mode == "FULL" and gate["can_optimize"]:
            allowed = True
        elif mode == "LIMITED" and gate["can_optimize"]:
            allowed = True
        else:
            allowed = False

        # If allowed, record and store adjustments
        if allowed:
            self._gate.record_optimization(self._process_count)
            self._last_adjustments = opt.get("adjustments", {})

        # Compose reason
        reasons = []
        if not gate["can_optimize"]:
            reasons.append(gate["reason"])
        if permission["mode"] != "FULL":
            reasons.append(permission["reason"])
        if clamped_result["clamped"]:
            reasons.append(f"Clamped: {', '.join(clamped_result['violations'])}")
        reason = "; ".join(reasons) if reasons else "Optimization allowed"

        return {
            "meta_decision": {
                "allowed": allowed,
                "mode": mode,
                "health_score": health["health_score"],
                "drift_status": drift.get("severity", "none"),
                "cooldown": gate["cooldown_tasks"],
            },
            "clamped_changes": clamped_result["adjusted_changes"],
            "snapshot_action": snapshot_action,
            "reason": reason,
        }

    # ═══════════════════════════════════════════════════════════════════
    # Query API
    # ═══════════════════════════════════════════════════════════════════

    def get_health_monitor(self) -> SystemHealthMonitor:
        return self._health_monitor

    def get_permission_engine(self) -> EvolutionPermissionEngine:
        return self._permission_engine

    def get_gate(self) -> OptimizationGate:
        return self._gate

    def get_clamp(self) -> EvolutionClamp:
        return self._clamp

    def get_snapshot_manager(self) -> SnapshotManager:
        return self._snapshot_manager

    def get_process_count(self) -> int:
        return self._process_count

    def get_last_adjustments(self) -> dict:
        return _deep_copy_dict(self._last_adjustments)


# ═══════════════════════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _deep_copy_dict(d: dict) -> dict:
    """简单深拷贝 nested dict（只处理原始值）。"""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _deep_copy_dict(v)
        elif isinstance(v, list):
            result[k] = list(v)
        else:
            result[k] = v
    return result


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
