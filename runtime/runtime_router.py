"""Runtime Router v1 — 自适应运行时路由

路由决策统一委托给 SystemDirectiveEngine.classify_intent()。
Router 不自作意图判断，只根据 SDE 的分类结果 dispatch。

简单对话 → direct LLM response (跳过 runtime)
复杂任务 → full DVexa runtime pipeline
"""

from __future__ import annotations

from governance.system_directive_engine import (
    _classify_intent,
    _estimate_complexity,
    RuntimeMode,
)

# Router 只询问 SDE，不自建关键词列表
# 关键词定义统一在 governance/system_directive_engine.py


def is_simple_conversation(user_input: str) -> bool:
    """判断输入是否为简单聊天。

    委托 SystemDirectiveEngine.classify_intent() 做意图识别。
    Router 只做 dispatch，不做独立判断。
    """
    intent = _classify_intent(user_input)
    # 非 CHAT 模式 → 必须走完整 runtime
    if intent != RuntimeMode.CHAT:
        return False
    # CHAT 模式下，检查复杂度
    complexity = _estimate_complexity(user_input)
    # 低复杂度聊天 → 轻量路径
    return complexity < 0.3
