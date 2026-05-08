"""Governance Cost Model v1 — Cost-aware Execution Constraint Layer

为所有 step / tool / governance action 引入统一 cost 计量，
在 execution 前约束 plan 成本，防止高成本路径无限扩展。

红线:
  - 全部 deterministic（无 LLM）
  - 执行前约束，不是后处理日志
  - cost violation → rewrite，不允许 warning
  - ComplexityBudget 管结构，CostModel 管经济
"""

from __future__ import annotations

from typing import Any


# ─── 默认 cost table ──────────────────────────────────────────────────────────

_DEFAULT_COST_TABLE: dict[str, float] = {
    "llm": 3.0,
    "code_executor": 2.0,
    "http_request": 1.0,
    "github": 1.5,
    "security": 2.5,
    "governance_check": 0.5,
    "memory": 0.2,
}

_DEFAULT_MAX_PLAN_COST = 15.0
_DEFAULT_MAX_STEP_COST = 5.0


# ═══════════════════════════════════════════════════════════════════════════════
# GovernanceCostModel
# ═══════════════════════════════════════════════════════════════════════════════


class GovernanceCostModel:
    """治理成本模型 — Cost-aware execution control layer。

    四方法:
      1. estimate_step_cost   — 单 step 成本计算
      2. estimate_plan_cost   — plan 总成本 + 分解
      3. enforce_cost_limit   — 强制执行成本约束
      4. select_cost_efficient_plan — 多 plan 最优选择

    工具方法:
      - compute_skill_efficiency — success_rate / avg_cost
    """

    def __init__(self, cost_table: dict[str, float] | None = None,
                 max_plan_cost: float = _DEFAULT_MAX_PLAN_COST,
                 max_step_cost: float = _DEFAULT_MAX_STEP_COST):
        self.cost_table = dict(cost_table or _DEFAULT_COST_TABLE)
        self.max_plan_cost = max_plan_cost
        self.max_step_cost = max_step_cost

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def estimate_step_cost(self, step: dict) -> float:
        """计算单 step 成本。

        因子:
          - reasoning step → 固定 1.0
          - tool step → base_cost + complexity_factor + depth_penalty
        """
        step_type = step.get("type", "")
        tool = step.get("tool", "")

        if step_type == "reasoning" or not tool:
            return 1.0

        base_cost = self.cost_table.get(tool, 1.0)

        action = step.get("action", "")
        complexity_factor = min(1.0, len(action) / 100.0) * 0.5

        depth = step.get("_depth", 0)
        depth_penalty = 0.1 * depth

        return round(base_cost + complexity_factor + depth_penalty, 2)

    def estimate_plan_cost(self, plan: dict) -> dict:
        """计算 plan 总成本及分解。

        Returns:
            {total_cost, step_costs, over_budget, dependency_penalty, fanout_penalty}
        """
        if not plan or "steps" not in plan:
            return _empty_cost_result(self.max_plan_cost)

        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            return _empty_cost_result(self.max_plan_cost)

        step_costs = [self.estimate_step_cost(s) for s in steps]
        subtotal = sum(step_costs)

        # dependency penalty: 连续相同 tool 的深度
        max_depth = 0
        current_depth = 0
        prev_tool = ""
        for s in steps:
            t = s.get("tool", "")
            if t and t == prev_tool:
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            else:
                current_depth = 0
            prev_tool = t
        dependency_penalty = round(0.1 * max_depth, 2)

        # fanout penalty: 不同工具数量
        tools = {s.get("tool", "") for s in steps if s.get("tool")}
        fanout_penalty = round(0.2 * max(0, len(tools) - 1), 2)

        total_cost = round(subtotal + dependency_penalty + fanout_penalty, 2)

        return {
            "total_cost": total_cost,
            "step_costs": step_costs,
            "over_budget": total_cost > self.max_plan_cost,
            "dependency_penalty": dependency_penalty,
            "fanout_penalty": fanout_penalty,
        }

    def enforce_cost_limit(self, plan: dict) -> dict:
        """强制执行成本约束，返回重写后的 plan。

        策略:
          1. 超 max_step_cost 的 step → downgrade to reasoning
          2. 仍超 max_plan_cost → 按价值排序，逐步降级/移除低价值步骤
        """
        if not plan or "steps" not in plan:
            return plan

        steps = list(plan.get("steps", []))
        if not isinstance(steps, list) or not steps:
            return plan

        modified = False

        # Phase 1: 高成本 step 降级
        new_steps = []
        for s in steps:
            if self.estimate_step_cost(s) > self.max_step_cost:
                new_steps.append(_downgrade_step(s))
                modified = True
            else:
                new_steps.append(s)

        # Phase 2: plan 总成本超限，逐步移除低价值步骤
        while len(new_steps) > 1:
            cost_info = self._compute_cost(new_steps)
            if not cost_info["over_budget"]:
                break

            # 按价值排序: value = action_length / cost
            scored = []
            for s in new_steps:
                sc = self.estimate_step_cost(s)
                action_len = len(s.get("action", ""))
                value = action_len / max(sc, 0.01)
                # reasoning 步骤价值折半（优先被移除）
                if s.get("type") == "reasoning" or not s.get("tool", ""):
                    value *= 0.5
                scored.append((value, sc, s))

            scored.sort(key=lambda x: x[0])
            worst = scored[0][2]

            if worst.get("type") == "reasoning" or not worst.get("tool", ""):
                new_steps.remove(worst)
            else:
                idx = new_steps.index(worst)
                new_steps[idx] = _downgrade_step(worst)

            modified = True

        if modified:
            return {**plan, "steps": new_steps, "_cost_enforced": True}
        return {**plan, "steps": new_steps}

    def select_cost_efficient_plan(self, plans: list[dict]) -> dict | None:
        """从多个 plan 中选择 cost/performance 最优者。

        metric = expected_success / total_cost
        """
        if not plans:
            return None

        best = None
        best_ratio = -1.0

        for p in plans:
            cost_info = self.estimate_plan_cost(p)
            cost = max(cost_info["total_cost"], 0.01)
            expected_success = p.get("_expected_success", 0.5)
            ratio = expected_success / cost

            if ratio > best_ratio:
                best_ratio = ratio
                best = p

        return best

    def compute_skill_efficiency(self, skill_name: str,
                                 stats: dict[str, float]) -> float:
        """计算 skill 效率: success_rate / avg_cost。

        Args:
            skill_name: 技能名（用于查找默认 cost）
            stats: 必须包含 success_rate, 可选 avg_cost

        Returns:
            efficiency 值 (越高越好)
        """
        success_rate = stats.get("success_rate", 0.5)
        avg_cost = stats.get(
            "avg_cost", self.cost_table.get(skill_name, 1.0),
        )
        if avg_cost <= 0:
            avg_cost = 0.01
        return round(success_rate / avg_cost, 4)

    # ═══════════════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════════════

    def _compute_cost(self, steps: list[dict]) -> dict:
        """内部用，只计算 steps 列表的成本。"""
        step_costs = [self.estimate_step_cost(s) for s in steps]
        subtotal = sum(step_costs)
        total_cost = round(subtotal, 2)
        return {
            "total_cost": total_cost,
            "step_costs": step_costs,
            "over_budget": total_cost > self.max_plan_cost,
        }


def _empty_cost_result(max_plan_cost: float) -> dict:
    return {
        "total_cost": 0.0,
        "step_costs": [],
        "over_budget": False,
        "dependency_penalty": 0.0,
        "fanout_penalty": 0.0,
    }


def _downgrade_step(step: dict) -> dict:
    """tool step → reasoning，保留 action 文本。"""
    new = dict(step, type="reasoning")
    new.pop("tool", None)
    new.pop("input", None)
    return new
