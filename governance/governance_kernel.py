"""Governance Kernel v2.6 — Unified Decision Core

取代 DecisionInjectionLayer + GovernanceStrategyLayer 双架构，
合并为统一的确定性治理内核。

内部流水线:
  1. Strategy Selection  — 根据任务/计划选择策略
  2. Plan Transformation — 按策略规则转换计划
  3. Hard Governance     — 4 检查点 + 策略覆盖
  4. Output Construction — 过滤后 plan + 决策 trace + 策略名

红线:
  - 不依赖 LLM
  - 完全确定性
  - 不修改 kernel / executor / tools
"""

from __future__ import annotations

from typing import Any


# ─── 工具名 ↔ 技能名 映射 ─────────────────────────────────────────────

_EXECUTOR_TO_SKILL: dict[str, str] = {
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
        "description": "高风险：ATS risk HIGH/CRITICAL 或 QUARANTINED 或多次 deny",
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
        "description": "探索：低置信度/新能力，LLM 推理优先",
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
        "description": "保守：金融/安全/网络任务，减少工具执行",
    },
}

_CONSERVATIVE_KEYWORDS = [
    "金融", "财务", "交易", "支付", "转账", "汇款",
    "security", "安全", "密码", "credential", "token", "密钥",
    "external", "网络请求", "api调用", "curl",
    "http", "https", "网络", "防火墙", "vpn",
]

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# ═══════════════════════════════════════════════════════════════════════
# GovernanceKernel
# ═══════════════════════════════════════════════════════════════════════


class GovernanceKernel:
    """统一决策内核 — DVexa governance 的唯一入口。

    用法:
        kernel = GovernanceKernel(governor, ats)
        result = kernel.process(task_context, raw_plan)
        # → {"filtered_plan": ..., "strategy": "...", "decisions": [...]}

    v1.9: Capability Awareness — 只观察+限制，不修改 capability。
    """

    def __init__(self, skill_governor=None, ats=None, tool_policy=None,
                 stabilizer=None, complexity_budget=None, cost_model=None,
                 global_optimizer=None, stability_layer=None,
                 capability_registry=None):
        self._governor = skill_governor
        self._ats = ats
        self._tool_policy = tool_policy
        self._stabilizer = stabilizer
        self._complexity_budget = complexity_budget
        self._cost_model = cost_model
        self._global_optimizer = global_optimizer
        self._stability_layer = stability_layer
        self._capability_registry = capability_registry

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def process(self, task: dict, plan: dict) -> dict:
        """统一决策入口。

        步骤:
          1. Strategy Selection — 确定性策略选择
          2-3. Hard Governance  — 4 检查点 + 策略覆盖 + 重排序
          4. Output            — 构造最终返回

        Args:
            task: 任务上下文（字段 as-is 用于策略检测）
            plan: Planner 原始输出

        Returns:
            {"filtered_plan": {...}, "strategy": "...", "decisions": [...]}
        """
        # ── HARD GOVERNANCE (deterministic, replayable) ─────────────────
        # Step 0: Complexity Budget (pre-control)
        if self._complexity_budget:
            budget = self._complexity_budget.assign_budget(task)
            plan = self._complexity_budget.check_plan(plan, budget)
            plan = self._complexity_budget.enforce(plan, budget)


        # Step 0.5: Cost Model (economic constraint)
        if self._cost_model:
            cost_info = self._cost_model.estimate_plan_cost(plan)
            if cost_info["over_budget"]:
                plan = self._cost_model.enforce_cost_limit(plan)
            plan["_cost_info"] = cost_info

        # Step 0.6: Capability Awareness (v1.9)
        # 只观察+限制，不修改 capability 本身
        capability_decisions: list[dict] = []
        if self._capability_registry:
            capability_decisions = self._check_capability_awareness(plan)

        # Step 1: Strategy Selection
        strategy = self._select_strategy(task, plan)

        # Capability awareness: quarantined capabilities force STRICT
        quarantined_found = any(
            d["action"] == "block" for d in capability_decisions
        )
        if quarantined_found and strategy != "STRICT":
            strategy = "STRICT"
            capability_decisions.append({
                "step_id": 0, "action": "info",
                "checkpoint": "capability_awareness",
                "reason": "Quarantined capability detected — strategy forced to STRICT",
            })

        config = self._resolve_config(strategy)

        if not plan or "steps" not in plan:
            return {
                "filtered_plan": plan,
                "strategy": strategy,
                "decisions": [],
            }

        # Steps 2-3: Transform + Enforce
        decisions: list[dict] = []
        filtered: list[dict] = []

        for step in plan["steps"]:
            step_id = step.get("id", 0)
            tool_name = step.get("tool", "")
            action_text = step.get("action", "")
            skill_name = _to_skill_name(tool_name) if tool_name else ""

            step_decisions: list[dict] = []

            # ── HARD: Checkpoint 1 — ToolPolicy ───────────────────────
            d = self._check_tool_policy(skill_name, tool_name, step_id,
                                        action_text, config)
            step_decisions.append(d)
            if d["action"] == "block":
                decisions.extend(step_decisions)
                continue
            if d["action"] == "reroute":
                step = dict(step, tool=d["reroute_to"])
                tool_name = step["tool"]
                skill_name = _to_skill_name(tool_name)

            # ── HARD: Checkpoint 2 — ATS ────────────────────────────
            d = self._check_ats(action_text, step_id, config)
            step_decisions.append(d)
            if d["action"] == "block":
                decisions.extend(step_decisions)
                continue
            if d["action"] == "downgrade":
                step = self._downgrade_step(step)
                decisions.extend(step_decisions)
                filtered.append(step)
                continue

            # ── HARD: Checkpoint 3 — SkillScore ─────────────────────
            d = self._check_skill_score(skill_name, step_id, config)
            step_decisions.append(d)
            if d["action"] == "downgrade":
                step = self._downgrade_step(step)

            # ── HARD: Checkpoint 4 — Lifecycle ──────────────────────
            d = self._check_lifecycle(skill_name, step_id, config)
            step_decisions.append(d)
            if d["action"] == "block":
                decisions.extend(step_decisions)
                continue
            if d["action"] == "downgrade":
                step = self._downgrade_step(step)
                decisions.extend(step_decisions)
                filtered.append(step)
                continue

            # ── HARD: Checkpoint 4.5 — Capability Awareness ──────────
            # 查询 capability taxonomy 中该 skill 的 maturity/risk
            d = self._check_capability_for_step(skill_name, step_id)
            if d:
                step_decisions.append(d)
                if d["action"] == "block":
                    decisions.extend(step_decisions)
                    continue
                if d["action"] == "downgrade":
                    step = self._downgrade_step(step)
                    decisions.extend(step_decisions)
                    filtered.append(step)
                    continue

            # ── SOFT: Checkpoint 5 — Strategy Override ───────────────
            if config.get("prefer_reasoning") and tool_name \
               and step.get("type") != "reasoning":
                step = self._downgrade_step(step)
                step_decisions.append({
                    "step_id": step_id,
                    "action": "downgrade",
                    "reason": f"策略 {strategy}: 优先 LLM 推理",
                })

            # ── Default: allow ─────────────────────────────────────────
            if not any(d["action"] not in ("allow",)
                       for d in step_decisions):
                step_decisions.append({
                    "step_id": step_id,
                    "action": "allow",
                    "reason": f"策略 {strategy} 全部通过",
                })

            decisions.extend(step_decisions)
            filtered.append(step)

        # Post-process: reorder
        if config.get("reorder_enabled", True):
            filtered = self._reorder_steps(filtered)

        # Post-process: stabilize (convergence layer)
        if self._stabilizer:
            filtered_plan = {**plan, "steps": filtered}
            filtered_plan = self._stabilizer.stabilize_plan(filtered_plan)
            decisions = self._stabilizer.stabilize_decisions(decisions)
        else:
            filtered_plan = {**plan, "steps": filtered}

        return {
            "filtered_plan": filtered_plan,
            "strategy": strategy,
            "decisions": decisions,
            "capability_decisions": capability_decisions,
        }

    def inject(self, plan: dict, task_context: dict | None = None) -> dict:
        """向后兼容接口，与 DecisionInjectionLayer.inject() 签名一致。

        Returns:
            {"filtered_plan": ..., "decisions": [...], "strategy_used": "..."}
        """
        if plan is None or not isinstance(plan, dict):
            return {"filtered_plan": plan, "decisions": []}
        result = self.process(task_context or {}, plan)
        return {
            "filtered_plan": result["filtered_plan"],
            "decisions": result["decisions"],
            "strategy_used": result["strategy"],
        }

    # ═══════════════════════════════════════════════════════════════════
    # Strategy Selection (deterministic)
    # ═══════════════════════════════════════════════════════════════════

    def _select_strategy(self, task: dict, plan: dict) -> str:
        """确定性策略选择。优先级: STRICT > CONSERVATIVE > EXPLORATION > BALANCED"""
        if self._detect_strict(plan):
            return "STRICT"
        if self._detect_conservative(task):
            return "CONSERVATIVE"
        if self._detect_exploration(plan):
            return "EXPLORATION"
        return "BALANCED"

    def _detect_strict(self, plan: dict) -> bool:
        """STRICT 触发条件: ATS HIGH/CRITICAL / QUARANTINED / 多次 deny"""
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

        if self._governor:
            for step in plan.get("steps", []):
                tool_name = step.get("tool", "")
                if not tool_name:
                    continue
                status = self._governor.get_status(_to_skill_name(tool_name))
                sv = status.value if hasattr(status, "value") else str(status)
                if sv == "quarantined":
                    return True

            denied = sum(
                1 for t in ("llm", "code", "http", "github", "security")
                if not self._governor.check_skill_allowed(t)
            )
            if denied >= 2:
                return True

        return False

    def _detect_conservative(self, task: dict) -> bool:
        """CONSERVATIVE 触发条件: 关键词匹配 / 重复失败"""
        task_text = " ".join(str(v) for v in task.values() if isinstance(v, str))
        task_lower = task_text.lower()
        for kw in _CONSERVATIVE_KEYWORDS:
            if kw in task_lower or kw in task_text:
                return True

        if self._governor:
            for skill in ("llm", "code", "http", "github", "security"):
                score = self._governor.get_score(skill)
                if score and hasattr(score, "consecutive_failures") \
                   and score.consecutive_failures > 2:
                    return True
        return False

    def _detect_exploration(self, plan: dict) -> bool:
        """EXPLORATION 触发条件: 未知工具 / 低分 / 首次使用"""
        if not self._governor:
            return False
        for step in plan.get("steps", []):
            tool_name = step.get("tool", "")
            if not tool_name:
                continue
            if tool_name not in _EXECUTOR_TO_SKILL:
                return True
            score = self._governor.get_score(_to_skill_name(tool_name))
            if score and score.combined_score < 0.3:
                return True
            if score and score.usage == 0:
                return True
        return False

    # ═══════════════════════════════════════════════════════════════════
    # Capability Awareness (v1.9)
    # ═══════════════════════════════════════════════════════════════════

    def _check_capability_awareness(self, plan: dict) -> list[dict]:
        """检查计划中涉及的 capability 状态。

        红线: 只观察+限制，不修改 capability。
        - quarantined → 自动阻断对应的 tool
        - experimental → 记录警告（后续策略提升强度）
        - high_risk → 记录警告
        """
        decisions: list[dict] = []
        if not self._capability_registry:
            return decisions

        for step in plan.get("steps", []):
            tool_name = step.get("tool", "")
            skill_name = _to_skill_name(tool_name) if tool_name else ""
            if not skill_name:
                continue

            # 查找对应的 capability nodes
            matches = self._capability_registry.search(keyword=skill_name)
            for node in matches:
                if node.maturity == "quarantined":
                    decisions.append({
                        "step_id": step.get("id", 0),
                        "action": "block",
                        "checkpoint": "capability_awareness",
                        "reason": f"Capability '{node.name}' is QUARANTINED — blocked by taxonomy",
                    })
                elif node.maturity == "experimental":
                    decisions.append({
                        "step_id": step.get("id", 0),
                        "action": "warn",
                        "checkpoint": "capability_awareness",
                        "reason": f"Capability '{node.name}' is EXPERIMENTAL — increased governance strength",
                    })
                elif node.risk_level in ("high", "critical"):
                    decisions.append({
                        "step_id": step.get("id", 0),
                        "action": "warn",
                        "checkpoint": "capability_awareness",
                        "reason": f"Capability '{node.name}' is HIGH RISK — monitor closely",
                    })

        return decisions

    # ═══════════════════════════════════════════════════════════════════
    # 4 Checkpoints + Strategy Override
    # ═══════════════════════════════════════════════════════════════════

    def _check_tool_policy(self, skill_name: str, tool_name: str,
                           step_id: int, action_text: str,
                           config: dict) -> dict:
        """Checkpoint 1: ToolPolicy + 策略覆盖。"""
        if not self._governor:
            return {"step_id": step_id, "action": "allow",
                    "reason": "no governor"}

        # 策略覆盖: CONSERVATIVE 阻断网络工具
        if config.get("block_network_tools") \
           and tool_name in ("http_request", "github"):
            return {"step_id": step_id, "action": "block",
                    "reason": f"策略 {config['label']}: 网络工具 '{tool_name}' 被禁止"}

        # 策略覆盖: 阻止未知工具
        if config.get("block_unknown_tools") \
           and tool_name not in _EXECUTOR_TO_SKILL:
            return {"step_id": step_id, "action": "reroute", "reroute_to": "llm",
                    "reason": f"策略 {config['label']}: 未知工具 '{tool_name}' reroute 到 llm"}

        allowed = self._governor.check_skill_allowed(skill_name)
        if not allowed:
            return {"step_id": step_id, "action": "reroute", "reroute_to": "llm",
                    "reason": f"工具 '{skill_name}' 被策略禁止，reroute 到 llm"}

        return {"step_id": step_id, "action": "allow",
                "reason": f"工具 '{skill_name}' 策略允许"}

    def _check_ats(self, action_text: str, step_id: int,
                   config: dict) -> dict:
        """Checkpoint 2: ATS + 可配置风险阈值。"""
        if not self._ats or not action_text:
            return {"step_id": step_id, "action": "allow",
                    "reason": "no ATS or no action"}

        report = self._ats.run(action_text, {})
        if not report.passed:
            return {"step_id": step_id, "action": "block",
                    "reason": f"ATS 阻断: {report.summary}"}

        rlv = (report.risk_level.value
               if hasattr(report.risk_level, "value")
               else str(report.risk_level))
        threshold = config.get("ats_risk_threshold", "high")
        if _RISK_ORDER.get(rlv, 0) >= _RISK_ORDER.get(threshold, 2):
            return {"step_id": step_id, "action": "downgrade",
                    "reason": f"ATS 风险 {rlv}(阈值 {threshold}), 降级"}

        return {"step_id": step_id, "action": "allow",
                "reason": f"ATS 通过 (风险 {rlv})"}

    def _check_skill_score(self, skill_name: str, step_id: int,
                           config: dict) -> dict:
        """Checkpoint 3: SkillScore + 可配置阈值。"""
        if not self._governor:
            return {"step_id": step_id, "action": "allow",
                    "reason": "no governor"}

        score_obj = self._governor.get_score(skill_name)
        if score_obj is None:
            return {"step_id": step_id, "action": "allow",
                    "reason": f"'{skill_name}' 无评分"}

        threshold = config.get("skill_score_threshold", 0.3)
        cs = score_obj.combined_score
        if cs < threshold:
            return {"step_id": step_id, "action": "downgrade",
                    "reason": f"'{skill_name}' 评分 {cs:.2f} < {threshold:.1f}, 降级"}

        return {"step_id": step_id, "action": "allow",
                "reason": f"'{skill_name}' 评分 {cs:.2f} >= {threshold:.1f}"}

    def _check_lifecycle(self, skill_name: str, step_id: int,
                         config: dict) -> dict:
        """Checkpoint 4: Lifecycle + 策略覆盖 experimental。"""
        if not self._governor or not skill_name:
            return {"step_id": step_id, "action": "allow",
                    "reason": "no governor or no skill"}

        status = self._governor.get_status(skill_name)
        sv = status.value if hasattr(status, "value") else str(status)

        if sv == "quarantined":
            return {"step_id": step_id, "action": "block",
                    "reason": f"skill '{skill_name}' QUARANTINED"}
        if sv == "removed":
            return {"step_id": step_id, "action": "block",
                    "reason": f"skill '{skill_name}' REMOVED"}
        if sv == "degraded":
            return {"step_id": step_id, "action": "downgrade",
                    "reason": f"skill '{skill_name}' DEGRADED"}

        if sv == "experimental":
            act = config.get("lifecycle_experimental_action", "allow")
            if act == "downgrade":
                return {"step_id": step_id, "action": "downgrade",
                        "reason": f"策略 {config['label']}: experimental 降级"}
            return {"step_id": step_id, "action": "allow",
                    "reason": f"skill '{skill_name}' experimental, 策略允许"}

        return {"step_id": step_id, "action": "allow",
                "reason": f"skill '{skill_name}' 状态 {sv} OK"}

    def _check_capability_for_step(self, skill_name: str, step_id: int) -> dict | None:
        """Checkpoint 4.5: Capability Taxonomy awareness。

        只观察+限制，不修改 capability 本身。
        - quarantined → block
        - experimental → downgrade (提升治理强度)
        - high_risk → 记录但允许通过
        """
        if not self._capability_registry or not skill_name:
            return None

        matches = self._capability_registry.search(keyword=skill_name)
        for node in matches:
            if node.maturity == "quarantined":
                return {
                    "step_id": step_id, "action": "block",
                    "checkpoint": "capability_awareness",
                    "reason": f"Capability '{node.name}' is QUARANTINED in taxonomy",
                }
            if node.maturity == "experimental":
                return {
                    "step_id": step_id, "action": "downgrade",
                    "checkpoint": "capability_awareness",
                    "reason": f"Capability '{node.name}' is EXPERIMENTAL — governance strengthened",
                }
            if node.risk_level in ("high", "critical"):
                return {
                    "step_id": step_id, "action": "warn",
                    "checkpoint": "capability_awareness",
                    "reason": f"Capability '{node.name}' is HIGH RISK — monitoring",
                }
        return None

    # ═══════════════════════════════════════════════════════════════════
    # Utilities
    # ═══════════════════════════════════════════════════════════════════

    def _reorder_steps(self, steps: list[dict]) -> list[dict]:
        """按评分重排序: reasoning 优先，tool 按 score 降序。"""
        if not self._governor or len(steps) <= 1:
            return steps

        def key(step: dict) -> tuple:
            t = step.get("type", "")
            if t == "reasoning" or not step.get("tool"):
                return (0, 0)
            score_obj = self._governor.get_score(_to_skill_name(step["tool"]))
            return (1, -(score_obj.combined_score if score_obj else 0.5))

        return sorted(steps, key=key)

    @staticmethod
    def _downgrade_step(step: dict) -> dict:
        """tool → reasoning，移除 tool/input。"""
        new = dict(step, type="reasoning")
        new.pop("tool", None)
        new.pop("input", None)
        return new

    @staticmethod
    def _resolve_config(strategy: str) -> dict:
        return dict(_STRATEGY_CONFIGS.get(strategy,
                                          _STRATEGY_CONFIGS["BALANCED"]))
