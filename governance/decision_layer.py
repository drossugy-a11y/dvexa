"""Governance Decision Injection Layer v1 (Wrapper)

v2.6: 内部实现已委托给 GovernanceKernel。
保留此类仅用于向后兼容。

新代码应直接使用 GovernanceKernel。
"""

from __future__ import annotations

from governance.governance_kernel import (
    GovernanceKernel,
    _to_skill_name,
    _EXECUTOR_TO_SKILL,
)


# ─── 重新导出 ─────────────────────────────────────────────────────────

_EXECUTOR_TO_SKILL = _EXECUTOR_TO_SKILL
_to_skill_name = _to_skill_name


# ─── DecisionInjectionLayer (thin wrapper) ─────────────────────────────


class DecisionInjectionLayer:
    """Governance Decision Injection Layer.

    v2.6: 内部使用 GovernanceKernel。
    保留此接口以保持测试和 GovernanceExecutorWrapper 的兼容性。

    Args:
        governor: SkillGovernor 实例
        ats: AssimilationTestSystem 实例
        strategy_layer: 已弃用，仅保留参数兼容
    """

    def __init__(self, governor=None, ats=None, strategy_layer=None):
        self._kernel = GovernanceKernel(
            skill_governor=governor,
            ats=ats,
        )
        # 为兼容 _build_governance_state / _reorder_steps 等直接调用
        self._governor = governor
        self._ats = ats

    def inject(self, plan: dict, task_context: dict | None = None) -> dict:
        """委托 GovernanceKernel.inject()。"""
        return self._kernel.inject(plan, task_context)

    def _build_governance_state(self) -> dict:
        """收集当前治理状态快照。"""
        state: dict = {"statuses": {}, "scores": {}}
        if self._governor:
            for name in ("llm", "code", "http", "github", "security"):
                state["statuses"][name] = str(self._governor.get_status(name))
                score = self._governor.get_score(name)
                if score:
                    state["scores"][name] = {
                        "combined_score": score.combined_score,
                        "usage": score.usage,
                        "consecutive_failures": score.consecutive_failures,
                    }
        return state

    def _reorder_steps(self, steps: list[dict]) -> list[dict]:
        return self._kernel._reorder_steps(steps)

    def _downgrade_step(self, step: dict) -> dict:
        return self._kernel._downgrade_step(step)

    def _check_lifecycle(self, skill_name: str, step_id: int) -> dict:
        return self._kernel._check_lifecycle(
            skill_name, step_id,
            self._kernel._resolve_config("BALANCED"),
        )

    def _check_tool_policy(self, skill_name: str, step_id: int,
                           action_text: str) -> dict:
        return self._kernel._check_tool_policy(
            skill_name, "", step_id, action_text,
            self._kernel._resolve_config("BALANCED"),
        )

    def _check_ats(self, action_text: str, step_id: int) -> dict:
        return self._kernel._check_ats(
            action_text, step_id,
            self._kernel._resolve_config("BALANCED"),
        )

    def _check_skill_score(self, skill_name: str, step_id: int) -> dict:
        return self._kernel._check_skill_score(
            skill_name, step_id,
            self._kernel._resolve_config("BALANCED"),
        )


# ─── GovernanceExecutorWrapper ────────────────────────────────────────────


class GovernanceExecutorWrapper:
    """Governance-aware Executor 包装器。

    在 planner 输出和 executor 执行之间注入治理决策。
    对 kernel 透明 — 实现 Executor 的 plan_task/execute_step 接口。

    接受 GovernanceKernel 或 DecisionInjectionLayer（均有 inject() 方法）。
    """

    def __init__(self, executor, decision_layer):
        self._executor = executor
        self._decision_layer = decision_layer
        # Kernel 直接访问 executor.agent.replan()
        self.agent = executor.agent

    def plan_task(self, task_input: str) -> dict:
        """plan_task 注入点：原始 plan → decision injection → filtered plan。"""
        raw_plan = self._executor.plan_task(task_input)
        result = self._decision_layer.inject(raw_plan)
        return result["filtered_plan"]

    def execute_step(self, task_state, step: dict, context: dict) -> dict:
        """透传至原始 executor。"""
        return self._executor.execute_step(task_state, step, context)

    def __getattr__(self, name: str):
        """Fallback: 委托未定义属性到原始 executor。"""
        return getattr(self._executor, name)
