"""Governance Strategy Layer v1 (DEPRECATED)

⚠️ 已弃用: 此模块的功能已合并到 GovernanceKernel (governance/governance_kernel.py)。
    保留仅用于向后兼容。新代码请直接使用 GovernanceKernel。"""

from __future__ import annotations

from typing import Any


# ─── 工具名 ↔ 技能名 映射（复用 decision_layer 的定义） ──────────────

_EXECUTOR_TO_SKILL = {
    "code_executor": "code",
    "http_request": "http",
    "llm": "llm",
    "github": "github",
    "security": "security",
}


def _to_skill_name(tool_name: str) -> str:
    return _EXECUTOR_TO_SKILL.get(tool_name, tool_name)


# ─── 策略配置 ──────────────────────────────────────────────────────────

_STRATEGY_CONFIGS: dict[str, dict[str, Any]] = {
    "STRICT": {
        "label": "STRICT",
        "skill_score_threshold": 0.5,
        "ats_risk_threshold": "medium",
        "lifecycle_experimental_action": "downgrade",
        "block_unknown_tools": True,
        "block_network_tools": False,
        "prefer_reasoning": False,
        "reorder_enabled": True,
        "description": "高风险场景：ATS risk HIGH 或 QUARANTINED 或多次 deny",
    },
    "BALANCED": {
        "label": "BALANCED",
        "skill_score_threshold": 0.3,
        "ats_risk_threshold": "high",
        "lifecycle_experimental_action": "allow",
        "block_unknown_tools": False,
        "block_network_tools": False,
        "prefer_reasoning": False,
        "reorder_enabled": True,
        "description": "常规任务：正常过滤，按 score 重排序",
    },
    "EXPLORATION": {
        "label": "EXPLORATION",
        "skill_score_threshold": 0.2,
        "ats_risk_threshold": "critical",
        "lifecycle_experimental_action": "allow",
        "block_unknown_tools": False,
        "block_network_tools": False,
        "prefer_reasoning": True,
        "reorder_enabled": False,
        "description": "探索模式：低置信度/新能力，鼓励 LLM 推理优先",
    },
    "CONSERVATIVE": {
        "label": "CONSERVATIVE",
        "skill_score_threshold": 0.5,
        "ats_risk_threshold": "medium",
        "lifecycle_experimental_action": "downgrade",
        "block_unknown_tools": True,
        "block_network_tools": True,
        "prefer_reasoning": True,
        "reorder_enabled": True,
        "description": "保守模式：金融/安全/网络任务，减少工具执行",
    },
}

# 保守任务关键词
_CONSERVATIVE_KEYWORDS = [
    "金融", "财务", "交易", "支付", "转账", "汇款",
    "security", "安全", "密码", "credential", "token", "密钥",
    "external", "网络请求", "api调用", "curl",
    "http", "https", "网络", "防火墙", "vpn",
]


# ─── GovernanceStrategyLayer ───────────────────────────────────────────


class GovernanceStrategyLayer:
    """策略驱动的治理层。

    根据任务上下文和计划选择策略，然后按照策略配置执行治理检查。

    Args:
        skill_governor: SkillGovernor 实例
        ats: AssimilationTestSystem 实例
        tool_policy: ToolPolicy 实例（可选，用于策略检测）
    """

    def __init__(self, skill_governor=None, ats=None, tool_policy=None):
        self._governor = skill_governor
        self._ats = ats
        self._tool_policy = tool_policy

    # ── Public API ──────────────────────────────────────────────────────

    def select_strategy(self, task: dict, plan: dict) -> str:
        """确定性策略选择（无 LLM）。

        优先级: STRICT > CONSERVATIVE > EXPLORATION > BALANCED

        Args:
            task: 任务上下文，含 task/action/input 等字段
            plan: Planner 输出的 raw plan

        Returns:
            "STRICT" | "BALANCED" | "EXPLORATION" | "CONSERVATIVE"
        """
        if self._check_strict(plan):
            return "STRICT"
        if self._check_conservative(task):
            return "CONSERVATIVE"
        if self._check_exploration(plan):
            return "EXPLORATION"
        return "BALANCED"

    def apply_strategy(self, strategy: str, plan: dict,
                       governance_state: dict | None = None) -> dict:
        """按策略配置执行治理流程。

        处理流水线：
          1. ToolPolicy check（含策略覆盖）
          2. ATS check（可配置风险阈值）
          3. SkillScore evaluation（可配置分数阈值）
          4. Lifecycle check（可配置 experimental 行为）
          5. Strategy rule override（如 prefer_reasoning）

        Args:
            strategy: 策略名
            plan: 原始 plan
            governance_state: 当前治理状态（可选）

        Returns:
            {"filtered_plan": {...}, "decisions": [...], "strategy_used": "..."}
        """
        config = self._resolve_config(strategy)
        decisions: list[dict] = []
        filtered: list[dict] = []

        if not plan or "steps" not in plan:
            return {"filtered_plan": plan, "decisions": decisions,
                    "strategy_used": strategy}

        for step in plan.get("steps", []):
            step_id = step.get("id", 0)
            tool_name = step.get("tool", "")
            action_text = step.get("action", "")
            skill_name = _to_skill_name(tool_name) if tool_name else ""

            step_decisions: list[dict] = []

            # ── 1. ToolPolicy check ────────────────────────────────────
            d_tp = self._check_tool_policy(skill_name, tool_name, step_id,
                                           action_text, config)
            step_decisions.append(d_tp)
            if d_tp["action"] == "block":
                decisions.extend(step_decisions)
                continue
            if d_tp["action"] == "reroute":
                step = dict(step, tool=d_tp.get("reroute_to", "llm"))
                tool_name = step["tool"]
                skill_name = _to_skill_name(tool_name)
                step_decisions[-1] = d_tp  # already appended, keep it

            # ── 2. ATS check ───────────────────────────────────────────
            d_ats = self._check_ats(action_text, step_id, config)
            step_decisions.append(d_ats)
            if d_ats["action"] == "block":
                decisions.extend(step_decisions)
                continue
            if d_ats["action"] == "downgrade":
                step = self._downgrade_step(step)
                decisions.extend(step_decisions)
                filtered.append(step)
                continue

            # ── 3. SkillScore check ────────────────────────────────────
            d_ss = self._check_skill_score(skill_name, step_id, config)
            step_decisions.append(d_ss)
            if d_ss["action"] == "downgrade":
                step = self._downgrade_step(step)

            # ── 4. Lifecycle check ────────────────────────────────────
            d_lc = self._check_lifecycle(skill_name, step_id, config)
            step_decisions.append(d_lc)
            if d_lc["action"] == "block":
                decisions.extend(step_decisions)
                continue
            if d_lc["action"] == "downgrade":
                step = self._downgrade_step(step)
                decisions.extend(step_decisions)
                filtered.append(step)
                continue

            # ── 5. Strategy override ──────────────────────────────────
            if config.get("prefer_reasoning") and tool_name \
               and step.get("type") != "reasoning":
                step = self._downgrade_step(step)
                step_decisions.append({
                    "step_id": step_id,
                    "action": "downgrade",
                    "reason": f"策略 {strategy}: 优先使用 LLM 推理",
                })

            # ── Default: allow ─────────────────────────────────────────
            if not any(d["action"] not in ("allow",) for d in step_decisions):
                step_decisions.append({
                    "step_id": step_id,
                    "action": "allow",
                    "reason": f"策略 {strategy} 全部检查通过",
                })

            decisions.extend(step_decisions)
            filtered.append(step)

        # ── 后处理：重排序 ──────────────────────────────────────────────
        if config.get("reorder_enabled", True):
            filtered = self._reorder_steps(filtered)

        return {
            "filtered_plan": {**plan, "steps": filtered},
            "decisions": decisions,
            "strategy_used": strategy,
        }

    def get_strategy_config(self, strategy: str) -> dict:
        """获取策略配置（供 DecisionInjectionLayer 使用）。"""
        return self._resolve_config(strategy)

    # ── 策略检测 ──────────────────────────────────────────────────────

    def _check_strict(self, plan: dict) -> bool:
        """检测是否需要 STRICT 策略。"""
        # ATS risk HIGH/CRITICAL
        if self._ats:
            for step in plan.get("steps", []):
                action = step.get("action", "")
                if not action:
                    continue
                report = self._ats.run(action, {})
                if not report.passed:
                    return True
                rl = report.risk_level
                rlv = rl.value if hasattr(rl, "value") else str(rl)
                if rlv in ("critical", "high"):
                    return True

        # Lifecycle QUARANTINED present
        if self._governor:
            for step in plan.get("steps", []):
                tool_name = step.get("tool", "")
                if not tool_name:
                    continue
                skill_name = _to_skill_name(tool_name)
                status = self._governor.get_status(skill_name)
                sv = status.value if hasattr(status, "value") else str(status)
                if sv == "quarantined":
                    return True

        # Multiple tool DENY
        if self._governor:
            denied = 0
            for t in ("llm", "code", "http", "github", "security"):
                if not self._governor.check_skill_allowed(t):
                    denied += 1
            if denied >= 2:
                return True

        return False

    def _check_conservative(self, task: dict) -> bool:
        """检测是否需要 CONSERVATIVE 策略。"""
        task_text = " ".join(str(v) for v in task.values() if isinstance(v, str))
        task_lower = task_text.lower()

        # 保守关键词匹配
        for kw in _CONSERVATIVE_KEYWORDS:
            if kw in task_lower or kw in task_text:
                return True

        # 重复失败检测
        if self._governor:
            for skill in ("llm", "code", "http", "github", "security"):
                score = self._governor.get_score(skill)
                if score and hasattr(score, "consecutive_failures") \
                   and score.consecutive_failures > 2:
                    return True

        return False

    def _check_exploration(self, plan: dict) -> bool:
        """检测是否需要 EXPLORATION 策略。"""
        if not self._governor:
            return False

        for step in plan.get("steps", []):
            tool_name = step.get("tool", "")
            if not tool_name:
                continue
            skill_name = _to_skill_name(tool_name)

            # 未知工具
            if tool_name not in _EXECUTOR_TO_SKILL:
                return True

            # 低分技能
            score = self._governor.get_score(skill_name)
            if score and score.combined_score < 0.3:
                return True

            # 首次使用的技能
            if score and score.usage == 0:
                return True

        return False

    # ── 4 检查点实现（含策略覆盖） ─────────────────────────────────

    def _check_tool_policy(self, skill_name: str, tool_name: str,
                           step_id: int, action_text: str,
                           config: dict) -> dict:
        """ToolPolicy 检查 + 策略覆盖。"""
        if not self._governor:
            return {"step_id": step_id, "action": "allow",
                    "reason": "no governor"}

        # 策略覆盖：CONSERVATIVE 阻断网络工具
        if config.get("block_network_tools") and tool_name in ("http_request", "github"):
            return {"step_id": step_id, "action": "block",
                    "reason": f"策略 {config['label']}: 网络工具 '{tool_name}' 被禁止"}

        # 策略覆盖：阻止未知工具
        if config.get("block_unknown_tools") and tool_name not in _EXECUTOR_TO_SKILL:
            return {"step_id": step_id, "action": "reroute", "reroute_to": "llm",
                    "reason": f"策略 {config['label']}: 未知工具 '{tool_name}' reroute 到 llm"}

        allowed = self._governor.check_skill_allowed(skill_name)
        if not allowed:
            return {
                "step_id": step_id,
                "action": "reroute",
                "reroute_to": "llm",
                "reason": f"工具 '{skill_name}' 被策略禁止，reroute 到 llm",
            }

        return {"step_id": step_id, "action": "allow",
                "reason": f"工具 '{skill_name}' 策略允许"}

    def _check_ats(self, action_text: str, step_id: int,
                   config: dict) -> dict:
        """ATS 检查 + 可配置风险阈值。"""
        if not self._ats or not action_text:
            return {"step_id": step_id, "action": "allow",
                    "reason": "no ATS or no action"}

        report = self._ats.run(action_text, {})

        if not report.passed:
            return {"step_id": step_id, "action": "block",
                    "reason": f"ATS 阻断: {report.summary}"}

        rl = report.risk_level
        rlv = rl.value if hasattr(rl, "value") else str(rl)

        # 使用策略配置的风险阈值
        threshold = config.get("ats_risk_threshold", "high")

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        rl_order = risk_order.get(rlv, 0)
        threshold_order = risk_order.get(threshold, 2)

        if rl_order >= threshold_order:
            return {"step_id": step_id, "action": "downgrade",
                    "reason": f"ATS 风险 {rlv}(阈值 {threshold}), 降级为 reasoning"}

        return {"step_id": step_id, "action": "allow",
                "reason": f"ATS 通过 (风险 {rlv})"}

    def _check_skill_score(self, skill_name: str, step_id: int,
                           config: dict) -> dict:
        """SkillScore 检查 + 可配置阈值。"""
        if not self._governor:
            return {"step_id": step_id, "action": "allow",
                    "reason": "no governor"}

        score_obj = self._governor.get_score(skill_name)
        if score_obj is None:
            return {"step_id": step_id, "action": "allow",
                    "reason": f"'{skill_name}' 无评分（默认通过）"}

        threshold = config.get("skill_score_threshold", 0.3)
        cs = score_obj.combined_score
        if cs < threshold:
            return {"step_id": step_id, "action": "downgrade",
                    "reason": f"'{skill_name}' 评分 {cs:.2f} < {threshold:.1f}, 降级为 reasoning"}

        return {"step_id": step_id, "action": "allow",
                "reason": f"'{skill_name}' 评分 {cs:.2f} >= {threshold:.1f}"}

    def _check_lifecycle(self, skill_name: str, step_id: int,
                         config: dict) -> dict:
        """Lifecycle 检查 + 策略覆盖 experimental。"""
        if not self._governor or not skill_name:
            return {"step_id": step_id, "action": "allow",
                    "reason": "no governor or no skill"}

        status = self._governor.get_status(skill_name)
        sv = status.value if hasattr(status, "value") else str(status)

        if sv == "quarantined":
            return {"step_id": step_id, "action": "block",
                    "reason": f"skill '{skill_name}' 状态 QUARANTINED"}
        if sv == "removed":
            return {"step_id": step_id, "action": "block",
                    "reason": f"skill '{skill_name}' 状态 REMOVED"}
        if sv == "degraded":
            return {"step_id": step_id, "action": "downgrade",
                    "reason": f"skill '{skill_name}' 状态 DEGRADED, 降级"}

        # 策略覆盖 experimental
        if sv == "experimental":
            action = config.get("lifecycle_experimental_action", "allow")
            if action == "downgrade":
                return {"step_id": step_id, "action": "downgrade",
                        "reason": f"策略 {config['label']}: experimental skill 降级"}
            return {"step_id": step_id, "action": "allow",
                    "reason": f"skill '{skill_name}' experimental, 策略允许"}

        return {"step_id": step_id, "action": "allow",
                "reason": f"skill '{skill_name}' 状态 {sv} OK"}

    # ── 后处理 ──────────────────────────────────────────────────────

    def _reorder_steps(self, steps: list[dict]) -> list[dict]:
        """按评分重排序：reasoning 优先，tool 按 score 降序。"""
        if not self._governor or len(steps) <= 1:
            return steps

        def sort_key(step: dict) -> tuple:
            t = step.get("type", "")
            if t == "reasoning" or not step.get("tool"):
                return (0, 0)
            skill_name = _to_skill_name(step.get("tool", ""))
            score_obj = self._governor.get_score(skill_name)
            score_val = score_obj.combined_score if score_obj else 0.5
            return (1, -score_val)

        return sorted(steps, key=sort_key)

    # ── 工具方法 ──────────────────────────────────────────────────────

    @staticmethod
    def _downgrade_step(step: dict) -> dict:
        """将 tool 步骤降级为 reasoning。"""
        new = dict(step, type="reasoning")
        new.pop("tool", None)
        new.pop("input", None)
        return new

    @staticmethod
    def _resolve_config(strategy: str) -> dict:
        return dict(_STRATEGY_CONFIGS.get(strategy, _STRATEGY_CONFIGS["BALANCED"]))
