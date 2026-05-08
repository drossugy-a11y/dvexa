"""Complexity Budget v1 — Pre-execution Constraint Layer

在 plan 进入 GovernanceKernel 之前，分配复杂度预算并强制执行。
防止 step 无限增长、tool fan-out 扩散、决策链深度爆炸。

红线:
  - 全部 deterministic（无 LLM）
  - 前置控制，不是后处理
  - budget violation → modify or reject，不允许 warning
  - Stabilizer 退化为异常兜底
"""

from __future__ import annotations

from typing import Any

# ─── 预算类型 → 配置映射 ──────────────────────────────────────────────────

_BUDGET_PROFILES: dict[str, dict[str, int]] = {
    "simple": {
        "max_steps": 5,
        "max_tool_fanout": 2,
        "max_governance_depth": 3,
        "max_decision_nodes": 5,
    },
    "normal": {
        "max_steps": 8,
        "max_tool_fanout": 3,
        "max_governance_depth": 4,
        "max_decision_nodes": 10,
    },
    "analysis": {
        "max_steps": 10,
        "max_tool_fanout": 4,
        "max_governance_depth": 4,
        "max_decision_nodes": 12,
    },
    "network": {
        "max_steps": 6,
        "max_tool_fanout": 2,
        "max_governance_depth": 3,
        "max_decision_nodes": 8,
    },
}

_DEFAULT_BUDGET = _BUDGET_PROFILES["normal"]

# 任务类型检测关键词
_SIMPLE_KEYWORDS = ["hello", "hi", "简单", "basic", "simple", "test", "ping"]
_ANALYSIS_KEYWORDS = ["分析", "analyze", "research", "investigate", "比较",
                      "对比", "总结", "summarize", "研究", "评估"]
_NETWORK_KEYWORDS = ["http", "api", "curl", "fetch", "网络", "请求",
                     "download", "web", "网页"]

_KNOWN_TOOLS = frozenset({
    "llm", "code_executor", "http_request", "github", "security",
})


# ═══════════════════════════════════════════════════════════════════════════
# ComplexityBudget
# ═══════════════════════════════════════════════════════════════════════════


class ComplexityBudget:
    """复杂度预算控制器。

    在 plan 进入 kernel 决策管道前执行三件事:
      1. assign_budget  — 根据 task 分配预算配置
      2. check_plan     — 检查 plan 是否超限
      3. enforce        — 强制裁剪违反预算的 plan
    """

    def __init__(self, default_budget: dict | None = None):
        self.default_budget = default_budget or dict(_DEFAULT_BUDGET)

    # ═══════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════

    def assign_budget(self, task: dict) -> dict:
        """为 task 分配复杂度预算。

        基于任务文本关键词匹配预算类型:
          simple → analysis → network → normal (default)

        Returns:
            {"profile": "...", "max_steps": N, "max_tool_fanout": N, ...}
        """
        task_text = " ".join(
            str(v) for v in task.values() if isinstance(v, str)
        ).lower()

        profile_name = self._detect_profile(task_text)
        profile = _BUDGET_PROFILES.get(profile_name, _DEFAULT_BUDGET)

        return {"profile": profile_name, **profile}

    def check_plan(self, plan: dict, budget: dict) -> dict:
        """检查 plan 是否违反预算约束。

        Returns:
            plan 追加 _budget_violations 字段（无 violation 时空列表）
        """
        violations: list[dict] = []

        if not plan or "steps" not in plan:
            return {**plan, "_budget_violations": violations} if isinstance(plan, dict) else plan

        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            return {**plan, "_budget_violations": violations}

        # 检查 step 数量
        max_steps = budget.get("max_steps", 8)
        if len(steps) > max_steps:
            violations.append({
                "rule": "max_steps",
                "limit": max_steps,
                "actual": len(steps),
                "action": "truncate",
            })

        # 检查 tool fan-out
        max_fanout = budget.get("max_tool_fanout", 3)
        tools_used = set()
        for s in steps:
            t = s.get("tool", "")
            if t:
                tools_used.add(t)
        if len(tools_used) > max_fanout:
            violations.append({
                "rule": "max_tool_fanout",
                "limit": max_fanout,
                "actual": len(tools_used),
                "tools": sorted(tools_used),
                "action": "downgrade_excess",
            })

        # 检查 governance depth（基于 tool 链中 governance 类工具占比）
        gov_tools = {t for t in tools_used if t in ("security",)}
        max_gov = budget.get("max_governance_depth", 4)
        # governance depth = 连续 governance 操作的最大长度
        # 简化实现：检查 security tool 在 step 序列中的最长连续出现
        gov_depth = 0
        current_gov = 0
        for s in steps:
            if s.get("tool", "") in ("security",):
                current_gov += 1
                gov_depth = max(gov_depth, current_gov)
            else:
                current_gov = 0
        if gov_depth > max_gov:
            violations.append({
                "rule": "max_governance_depth",
                "limit": max_gov,
                "actual": gov_depth,
                "action": "reduce_depth",
            })

        return {**plan, "_budget_violations": violations}

    def enforce(self, plan: dict, budget: dict) -> dict:
        """强制裁剪 plan 以符合预算约束。

        操作顺序:
          1. 截断 step 到 max_steps
          2. 超限 tool → downgrade to reasoning
          3. governance depth 超限 → 合并 governance steps

        Returns:
            裁剪后的 plan
        """
        if not plan or "steps" not in plan:
            return plan

        steps = list(plan.get("steps", []))
        if not isinstance(steps, list):
            return plan

        max_steps = budget.get("max_steps", 8)
        max_fanout = budget.get("max_tool_fanout", 3)
        max_gov_depth = budget.get("max_governance_depth", 4)

        # Rule 1: 截断 step 数量
        if len(steps) > max_steps:
            steps = steps[:max_steps]

        # Rule 2: 限制 tool fan-out（超限的 tool → llm）
        tool_counts: dict[str, int] = {}
        for s in steps:
            t = s.get("tool", "")
            if t:
                tool_counts[t] = tool_counts.get(t, 0) + 1

        if len(tool_counts) > max_fanout:
            # 保留使用频率最高的 max_fanout 个工具
            sorted_tools = sorted(tool_counts, key=tool_counts.get, reverse=True)
            allowed_tools = set(sorted_tools[:max_fanout])
            for i, s in enumerate(steps):
                t = s.get("tool", "")
                if t and t not in allowed_tools and t != "":
                    steps[i] = dict(s, tool="llm")

        # Rule 3: 减少 governance depth（合并连续 security steps）
        new_steps: list[dict] = []
        security_run: list[dict] = []
        for s in steps:
            if s.get("tool", "") == "security":
                if len(security_run) >= max_gov_depth:
                    # 超限的 security step 跳过
                    continue
                security_run.append(s)
            else:
                if security_run:
                    new_steps.extend(security_run)
                    security_run = []
                new_steps.append(s)
        if security_run:
            new_steps.extend(security_run)

        return {**plan, "steps": new_steps}

    def estimate_complexity(self, plan: dict) -> float:
        """估算 plan 的复杂度评分 (0.0 ~ 1.0)。

        因子:
          - step count (0~0.4)
          - tool diversity (0~0.3)
          - dependency/action depth (0~0.3)
        """
        if not plan or "steps" not in plan:
            return 0.0

        steps = plan.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return 0.0

        # Step count factor: 0~0.4  (10+ steps = max 0.4)
        n = len(steps)
        step_factor = min(0.4, n / 25.0)

        # Tool diversity factor: 0~0.3  (5+ tools = max 0.3)
        tools = {s.get("tool", "") for s in steps if s.get("tool")}
        tool_factor = min(0.3, len(tools) / 15.0)

        # Action depth factor: 0~0.3
        # 基于 action 文本长度 ≈ 指令复杂度
        avg_action_len = sum(
            len(s.get("action", "")) for s in steps
        ) / max(len(steps), 1)
        depth_factor = min(0.3, avg_action_len / 200.0)

        return round(step_factor + tool_factor + depth_factor, 4)

    # ═══════════════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════════════

    def _detect_profile(self, task_text: str) -> str:
        """检测任务类型 → 预算 profile。

        ASCII 关键词用单词边界匹配（防 "hi" 匹配 "something"），
        CJK 关键词用子串匹配（中文无空格分隔）。
        """
        words = set(task_text.split())
        for kw in _SIMPLE_KEYWORDS:
            if (kw in words) if kw.isascii() else (kw in task_text):
                return "simple"
        for kw in _NETWORK_KEYWORDS:
            if (kw in words) if kw.isascii() else (kw in task_text):
                return "network"
        for kw in _ANALYSIS_KEYWORDS:
            if (kw in words) if kw.isascii() else (kw in task_text):
                return "analysis"
        return "normal"
