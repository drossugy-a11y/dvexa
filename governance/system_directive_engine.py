"""System Directive Engine — DVexa 顶层行为控制器

DVX System Directive Engine is the top-level behavioral controller of DVexa runtime.

It does NOT generate answers.
It decides HOW the system should behave before any LLM response happens.

It enforces:
- execution mode selection
- planning requirement
- tool usage decision
- streaming activation
- governance constraints

位置: User Input → SDE → GovernanceKernel → Planner → Executor → Tools → Stream
"""

from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
# Runtime Mode
# ═══════════════════════════════════════════════════════════════════════


class RuntimeMode(str, Enum):
    CHAT = "chat"        # 普通对话 — 无规划，轻推理
    TASK = "task"        # 执行任务 — 必须规划，深度推理，可流式
    TOOL = "tool"        # 工具调用 — 必须用工具，流式执行
    EXPLORE = "explore"  # 探索分析 — 深度推理，工具可选
    SYSTEM = "system"    # 系统级操作 — 全约束


# ═══════════════════════════════════════════════════════════════════════
# System Directive — 控制输出
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SystemDirective:
    mode: str                   # RuntimeMode value
    must_plan: bool             # 是否需要结构化规划
    must_use_tools: bool        # 是否必须用工具
    must_stream: bool           # 是否流式输出
    reasoning_level: str        # light | deep | full
    governance_level: str       # strict | balanced | loose

    def to_dict(self) -> dict:
        return asdict(self)

    def to_system_prompt(self) -> str:
        """生成注入 BaseAgent system prompt 的指令块。"""
        return (
            "DVEXA SYSTEM DIRECTIVE\n"
            "You are a DVX Runtime Agent, not a chatbot.\n"
            "You are controlled by SystemDirectiveEngine.\n\n"
            f"MODE: {self.mode}\n"
            f"MUST_PLAN: {self.must_plan}\n"
            f"MUST_USE_TOOLS: {self.must_use_tools}\n"
            f"MUST_STREAM: {self.must_stream}\n"
            f"REASONING_LEVEL: {self.reasoning_level}\n"
            f"GOVERNANCE_LEVEL: {self.governance_level}\n\n"
            "Rules:\n"
            f"- MUST_PLAN={self.must_plan}: {'output structured plan first' if self.must_plan else 'no plan required'}\n"
            f"- MUST_USE_TOOLS={self.must_use_tools}: {'prefer tools over reasoning-only answers' if self.must_use_tools else 'tools optional'}\n"
            f"- MUST_STREAM={self.must_stream}: {'output incremental execution steps' if self.must_stream else 'no streaming required'}\n"
            f"- MODE={self.mode}: {'system-level operation, not chat' if self.mode == 'system' else 'normal operation'}\n\n"
            "You are an execution runtime component inside DVexa OS.\n"
            "You do NOT behave like a general assistant."
        )


# ═══════════════════════════════════════════════════════════════════════
# Default Directive
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_DIRECTIVE = SystemDirective(
    mode=RuntimeMode.CHAT,
    must_plan=False,
    must_use_tools=False,
    must_stream=False,
    reasoning_level="light",
    governance_level="balanced",
)


# ═══════════════════════════════════════════════════════════════════════
# Intent & Complexity Classifiers
# ═══════════════════════════════════════════════════════════════════════


_TASK_KEYWORDS = [
    "how to build", "create", "implement", "develop", "build", "write code",
    "project", "refactor", "重构", "实现", "开发", "构建", "创建",
]

_TOOL_KEYWORDS = [
    "fix", "debug", "error", "bug", "修复", "调试",
    "run", "execute", "执行", "运行",
    "scan", "security", "安全扫描",
]

_EXPLORE_KEYWORDS = [
    "analyze", "research", "investigate", "explore", "分析", "研究",
    "what is", "how does", "explain", "解释", "说明",
]

_SYSTEM_PATTERNS = [
    r"^system[: ]",
    r"^/",
    r"^!",
    r"status",
    r"health",
]


def _classify_intent(user_input: str, context: dict | None = None) -> str:
    """确定性意图分类 — 不依赖 LLM。"""
    text = user_input.lower().strip()
    ctx = context or {}

    # System queries
    if ctx.get("system_query"):
        return RuntimeMode.SYSTEM
    for pat in _SYSTEM_PATTERNS:
        if re.match(pat, text):
            return RuntimeMode.SYSTEM

    # Task intent
    for kw in _TASK_KEYWORDS:
        if kw in text:
            return RuntimeMode.TASK

    # Tool intent
    for kw in _TOOL_KEYWORDS:
        if kw in text:
            return RuntimeMode.TOOL

    # Explore intent
    for kw in _EXPLORE_KEYWORDS:
        if kw in text:
            return RuntimeMode.EXPLORE

    return RuntimeMode.CHAT


def _estimate_complexity(user_input: str, context: dict | None = None) -> float:
    """估算任务复杂度 (0.0 ~ 1.0)。"""
    score = 0.0
    text = user_input

    # Length-based
    if len(text) > 500:
        score += 0.3
    elif len(text) > 200:
        score += 0.2

    # Keyword-based
    complexity_kw = ["multi-step", "复杂", "multiple", "comprehensive", "full",
                     "complete", "端到端", "全面", "pipe", "pipeline"]
    for kw in complexity_kw:
        if kw in text.lower():
            score += 0.1

    # Context-based
    ctx = context or {}
    steps = len(ctx.get("steps", []))
    if steps > 5:
        score += 0.2
    if ctx.get("has_history"):
        score += 0.1

    return min(score, 1.0)


# ═══════════════════════════════════════════════════════════════════════
# SystemDirectiveEngine
# ═══════════════════════════════════════════════════════════════════════


class SystemDirectiveEngine:
    """系统指令引擎 — 执行前的行为控制器。

    Pipeline:
      1. classify_intent()     → 意图识别
      2. evaluate_context()    → 运行时状态评估
      3. decide_mode()         → 模式决策
      4. enforce_constraints() → 约束强制执行
      5. generate_directive()  → 输出 SystemDirective
    """

    def __init__(self, governance_kernel: Any = None,
                 capability_registry: Any = None):
        self._governance = governance_kernel
        self._capabilities = capability_registry

    def process(self, user_input: str,
                context: dict | None = None) -> SystemDirective:
        """全流程: input → SystemDirective。"""
        intent = _classify_intent(user_input, context)
        state = self._evaluate_context(context)
        mode = self._decide_mode(intent, state)
        rules = self._enforce_constraints(mode, intent, state)
        return self._generate(mode, rules)

    # ── Context Evaluation ────────────────────────────────────────────

    @staticmethod
    def _evaluate_context(context: dict | None = None) -> dict:
        """评估运行时上下文状态。

        接受预计算的 complexity 值（用于测试），
        也接受 input 文本自动计算。
        """
        ctx = context or {}
        complexity = ctx.get("complexity")
        if complexity is None:
            complexity = _estimate_complexity(
                ctx.get("input", ""), context
            )
        return {
            "complexity": complexity,
            "has_history": bool(ctx.get("has_history", False)),
            "has_tools": bool(ctx.get("has_tools", True)),
            "is_degraded": ctx.get("governance_degraded", False),
            "task_count": ctx.get("task_count", 0),
        }

    # ── Mode Decision ─────────────────────────────────────────────────

    @staticmethod
    def _decide_mode(intent: str, state: dict) -> str:
        """基于意图 + 上下文状态决定执行模式。"""
        if intent == RuntimeMode.SYSTEM:
            return RuntimeMode.SYSTEM

        if intent == RuntimeMode.TASK:
            return RuntimeMode.TASK

        if intent == RuntimeMode.TOOL:
            return RuntimeMode.TOOL

        if intent == RuntimeMode.EXPLORE:
            return RuntimeMode.EXPLORE

        # CHAT intent: escalate if complexity high
        if state.get("complexity", 0) > 0.6:
            return RuntimeMode.TASK

        return RuntimeMode.CHAT

    # ── Constraint Enforcement ────────────────────────────────────────

    def _enforce_constraints(self, mode: str, intent: str,
                              state: dict) -> dict:
        """基于模式和状态强制执行约束规则。"""
        rules: dict[str, Any] = {
            "must_plan": False,
            "must_use_tools": False,
            "must_stream": False,
            "reasoning_level": "light",
            "governance_level": "balanced",
        }

        # Mode-based rules
        if mode == RuntimeMode.TASK:
            rules["must_plan"] = True
            rules["must_stream"] = True
            rules["reasoning_level"] = "deep"

        elif mode == RuntimeMode.TOOL:
            rules["must_plan"] = True
            rules["must_use_tools"] = True
            rules["must_stream"] = True
            rules["reasoning_level"] = "deep"

        elif mode == RuntimeMode.SYSTEM:
            rules["must_plan"] = True
            rules["must_use_tools"] = True
            rules["reasoning_level"] = "full"

        elif mode == RuntimeMode.EXPLORE:
            rules["reasoning_level"] = "full"

        # Governance override (degraded = enforce strict regardless of governance ref)
        if state.get("is_degraded"):
            rules["governance_level"] = "strict"
            rules["must_plan"] = True

        # Complexity override
        if state.get("complexity", 0) > 0.7:
            rules["must_plan"] = True
            rules["reasoning_level"] = "full"

        return rules

    # ── Directive Generation ──────────────────────────────────────────

    @staticmethod
    def _generate(mode: str, rules: dict) -> SystemDirective:
        return SystemDirective(
            mode=mode,
            must_plan=rules["must_plan"],
            must_use_tools=rules["must_use_tools"],
            must_stream=rules["must_stream"],
            reasoning_level=rules["reasoning_level"],
            governance_level=rules["governance_level"],
        )


# ═══════════════════════════════════════════════════════════════════════
# Convenience
# ═══════════════════════════════════════════════════════════════════════

def create_directive(user_input: str,
                     context: dict | None = None) -> SystemDirective:
    """单次调用便捷接口。"""
    engine = SystemDirectiveEngine()
    return engine.process(user_input, context)
