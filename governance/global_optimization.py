"""Global Optimization Loop v1 — System-level Self-Optimization Layer

让 DVexa 在长期运行中具备自动发现低效路径、自动调整结构、
自动收敛复杂度的能力。从"受控执行系统"升级为"自优化治理系统"。

红线:
  - 全部 deterministic（无 LLM）
  - 结构级优化，不参与单任务执行流
  - FeedbackEngine = 学习单次行为，GlobalOptimizationLoop = 学习整个系统
"""

from __future__ import annotations

from typing import Any


# ─── 默认阈值 ──────────────────────────────────────────────────────────────────

_MIN_CALLS_FOR_EFFICIENCY = 3
_LOW_EFFICIENCY_THRESHOLD = 0.3
_HIGH_VARIANCE_THRESHOLD = 0.15
_HIGH_FALLBACK_THRESHOLD = 0.20
_TOOL_COST_ADJUST_LOW = 1.30    # 低效 tool → 成本 +30%
_TOOL_COST_ADJUST_MED = 1.15    # 中低效 tool → 成本 +15%
_TOOL_COST_ADJUST_HIGH = 0.85   # 高效 tool → 成本 -15%
_STRATEGY_BIAS_STRONG = -0.2
_STRATEGY_BIAS_WEAK = -0.1


# ═══════════════════════════════════════════════════════════════════════════════
# GlobalOptimizationLoop
# ═══════════════════════════════════════════════════════════════════════════════


class GlobalOptimizationLoop:
    """全局自优化环 — System-level optimizer, not task-level。

    FeedbackEngine 记录单次行为，GlobalOptimizationLoop 学习整个系统。

    用法:
        loop = GlobalOptimizationLoop(skill_governor, cost_model, strategy_stats)
        result = loop.run(history)  # history = list[execution_record]
    """

    def __init__(self, skill_governor: Any, cost_model: Any,
                 strategy_stats: dict, meta_control_plane: Any = None):
        self._governor = skill_governor
        self._cost_model = cost_model
        self._strategy_stats = strategy_stats
        self._meta_control_plane = meta_control_plane
        self._optimization_count = 0
        self._adjustment_log: list[dict] = []

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def run(self, history: list[dict]) -> dict:
        """执行一轮全局优化：分析 → 检测 → 计算 → 应用。

        Args:
            history: 历史执行记录列表（来自 memory.get_all()）

        Returns:
            {"metrics": ..., "inefficiencies": ..., "adjustments": ...}
        """
        # ── Meta Control Plane Gate ──
        if self._meta_control_plane is not None:
            sys_state = self._build_state_for_meta(history)
            meta_result = self._meta_control_plane.process(
                sys_state, {"adjustments": {}}
            )
            if not meta_result["meta_decision"]["allowed"]:
                return {
                    "metrics": {},
                    "inefficiencies": {},
                    "adjustments": {},
                    "meta_blocked": True,
                    "meta_reason": meta_result["reason"],
                }

        metrics = self.analyze_system_metrics(history)
        inefficiencies = self.detect_inefficiencies(metrics)
        adjustments = self.compute_adjustments(inefficiencies)
        self.apply_optimizations(adjustments)

        self._optimization_count += 1
        self._adjustment_log.append({
            "round": self._optimization_count,
            "adjustments": adjustments,
        })

        return {
            "metrics": metrics,
            "inefficiencies": inefficiencies,
            "adjustments": adjustments,
        }

    # ═══════════════════════════════════════════════════════════════════
    # Analysis Pipeline
    # ═══════════════════════════════════════════════════════════════════

    def analyze_system_metrics(self, history: list[dict]) -> dict:
        """分析全局运行数据：tool usage、strategy 效果、fallback 频率。"""
        if not history:
            return {"tool_stats": {}, "tool_usage": {},
                    "strategy_effectiveness": {},
                    "fallback_rate": 0.0, "total_tasks": 0}

        tool_stats: dict[str, dict] = {}
        strategy_outcomes: dict[str, list[float]] = {}
        total_fallbacks = 0
        total_decisions = 0

        for record in history:
            steps = record.get("filtered_plan", {}).get("steps", []) \
                    or record.get("steps", [])
            success = record.get("success", record.get("passed", True))
            strategy = record.get("strategy", record.get("strategy_used", "BALANCED"))
            decisions = record.get("decisions", [])

            # Strategy outcomes
            if strategy not in strategy_outcomes:
                strategy_outcomes[strategy] = []
            strategy_outcomes[strategy].append(1.0 if success else 0.0)

            # Tool usage
            for step in steps:
                tool = step.get("tool", "")
                if not tool:
                    continue
                if tool not in tool_stats:
                    tool_stats[tool] = {"calls": 0, "successes": 0,
                                        "total_cost": 0.0}
                ts = tool_stats[tool]
                ts["calls"] += 1
                if success:
                    ts["successes"] += 1
                ts["total_cost"] += self._cost_model.estimate_step_cost(step)

            # Fallback tracking
            for d in decisions:
                total_decisions += 1
                if d.get("action") in ("reroute", "downgrade", "block"):
                    total_fallbacks += 1

        # Raw tool usage (unfiltered, for tests and inspection)
        tool_usage = {
            t: {"calls": s["calls"], "successes": s["successes"]}
            for t, s in tool_stats.items()
        }

        # Derive tool efficiency (filtered by minimum calls)
        tool_efficiency = {}
        for tool, ts in tool_stats.items():
            if ts["calls"] >= _MIN_CALLS_FOR_EFFICIENCY:
                sr = ts["successes"] / ts["calls"]
                ac = ts["total_cost"] / ts["calls"]
                eff = sr / max(ac, 0.01)
                tool_efficiency[tool] = {
                    "success_rate": round(sr, 4),
                    "avg_cost": round(ac, 4),
                    "efficiency": round(eff, 4),
                    "calls": ts["calls"],
                }

        # Derive strategy effectiveness
        strat_eff = {}
        for sname, outcomes in strategy_outcomes.items():
            n = len(outcomes)
            if n >= 1:
                mean = sum(outcomes) / n
                variance = (sum((o - mean) ** 2 for o in outcomes) / n
                           ) if n > 1 else 0.0
                effectiveness = mean * (1.0 / max(variance, 0.01))
                strat_eff[sname] = {
                    "success_rate": round(mean, 4),
                    "variance": round(variance, 4),
                    "effectiveness": round(effectiveness, 4),
                    "tasks": n,
                }

        fallback_rate = (total_fallbacks / max(total_decisions, 1))

        return {
            "tool_stats": tool_efficiency,
            "tool_usage": tool_usage,
            "strategy_effectiveness": strat_eff,
            "fallback_rate": round(fallback_rate, 4),
            "total_tasks": len(history),
        }

    def detect_inefficiencies(self, metrics: dict) -> dict:
        """识别低效结构：低效 tool、高方差策略、高 fallback 路径。"""
        inefficiencies: dict[str, list] = {
            "low_efficiency_tools": [],
            "high_variance_strategies": [],
            "high_fallback_path": False,
        }

        for tool, stats in metrics.get("tool_stats", {}).items():
            if stats["efficiency"] < _LOW_EFFICIENCY_THRESHOLD:
                inefficiencies["low_efficiency_tools"].append({
                    "tool": tool,
                    "efficiency": stats["efficiency"],
                    "success_rate": stats["success_rate"],
                    "avg_cost": stats["avg_cost"],
                })

        for sname, stats in metrics.get("strategy_effectiveness", {}).items():
            if stats["variance"] > _HIGH_VARIANCE_THRESHOLD:
                inefficiencies["high_variance_strategies"].append({
                    "strategy": sname,
                    "variance": stats["variance"],
                    "effectiveness": stats["effectiveness"],
                })

        if metrics.get("fallback_rate", 0) > _HIGH_FALLBACK_THRESHOLD:
            inefficiencies["high_fallback_path"] = True

        return inefficiencies

    def compute_adjustments(self, inefficiencies: dict) -> dict:
        """生成系统级调整：tool cost 调整、策略 bias、prune 建议。"""
        adjustments: dict[str, Any] = {
            "tool_cost_multipliers": {},
            "strategy_biases": {},
            "prune_suggestions": [],
            "round": self._optimization_count + 1,
        }

        for entry in inefficiencies.get("low_efficiency_tools", []):
            tool = entry["tool"]
            eff = entry["efficiency"]
            if eff < 0.15:
                adjustments["tool_cost_multipliers"][tool] = _TOOL_COST_ADJUST_LOW
            elif eff < _LOW_EFFICIENCY_THRESHOLD:
                adjustments["tool_cost_multipliers"][tool] = _TOOL_COST_ADJUST_MED

        for entry in inefficiencies.get("high_variance_strategies", []):
            sname = entry["strategy"]
            var = entry["variance"]
            adjustments["strategy_biases"][sname] = (
                _STRATEGY_BIAS_STRONG if var > 0.25 else _STRATEGY_BIAS_WEAK
            )

        return adjustments

    def apply_optimizations(self, adjustments: dict):
        """应用结构级优化到 system components。

        - cost_model.cost_table  → tool cost 调整
        - strategy_stats         → strategy bias 调整
        - skill_governor scores  → 基于效率调整
        """
        # ── Cost table tuning ─────────────────────────────────────────
        for tool, multiplier in adjustments.get("tool_cost_multipliers",
                                                {}).items():
            if tool in self._cost_model.cost_table:
                old = self._cost_model.cost_table[tool]
                self._cost_model.cost_table[tool] = round(old * multiplier, 2)

        # ── Strategy bias tuning ──────────────────────────────────────
        for sname, bias_delta in adjustments.get("strategy_biases", {}).items():
            if sname in self._strategy_stats:
                self._strategy_stats[sname]["bias"] = (
                    self._strategy_stats[sname].get("bias", 0.0) + bias_delta
                )
            else:
                self._strategy_stats[sname] = {"bias": bias_delta}

        # ── Skill governor score tuning ───────────────────────────────
        for entry in adjustments.get("tool_cost_multipliers", {}).items():
            tool = entry[0]
            try:
                score = self._governor.get_score(tool)
                if score is not None:
                    # 低效 → 降低 stability（间接影响 combined_score）
                    score.stability = max(0.1, score.stability - 0.05)
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════
    # Query API
    # ═══════════════════════════════════════════════════════════════════

    def get_optimization_count(self) -> int:
        return self._optimization_count

    def get_adjustment_log(self) -> list[dict]:
        return list(self._adjustment_log)

    def get_last_adjustment(self) -> dict | None:
        return self._adjustment_log[-1] if self._adjustment_log else None

    def _build_state_for_meta(self, history: list[dict]) -> dict:
        """为 MetaControlPlane 构建系统状态。"""
        strategy_counts: dict[str, int] = {}
        strategy_successes: dict[str, int] = {}
        for r in history:
            s = r.get("strategy", "BALANCED")
            strategy_counts[s] = strategy_counts.get(s, 0) + 1
            if r.get("success", True):
                strategy_successes[s] = strategy_successes.get(s, 0) + 1

        strategy_eff = {}
        for s, count in strategy_counts.items():
            suc = strategy_successes.get(s, 0)
            rate = suc / count if count > 0 else 0.5
            strategy_eff[s] = {"success_rate": round(rate, 4),
                               "variance": 0.0, "tasks": count}

        total_decisions = sum(len(r.get("decisions", [])) for r in history)
        fallbacks = sum(
            1 for r in history for d in r.get("decisions", [])
            if d.get("action") in ("reroute", "downgrade", "block")
        )
        fallback_rate = fallbacks / max(total_decisions, 1)

        return {
            "strategy_effectiveness": strategy_eff,
            "fallback_rate": round(fallback_rate, 4),
            "total_tasks": len(history),
            "cost_stability": 1.0,
            "rollback_rate": 0.0,
            "drift": {"drift_detected": False, "severity": "none"},
        }
