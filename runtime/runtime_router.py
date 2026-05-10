"""Runtime Router v1 — 自适应运行时路由

简单对话 → direct LLM response (跳过 runtime)
复杂任务 → full DVexa runtime pipeline
"""

from __future__ import annotations

# 任务/工具关键词 — 遇到这些词必须走完整 runtime
_TASK_KEYWORDS = [
    "代码", "实现", "构建", "帮我", "开发", "重构", "分析", "修复",
    "create", "implement", "build", "refactor", "analyze",
    "run", "execute", "scan", "security", "pipeline",
]


def is_simple_conversation(user_input: str) -> bool:
    """判断输入是否为简单聊天。

    简单聊天的特征：
    - 无需多步执行
    - 无需工具调用
    - 无需规划
    - 可以直接 LLM 回复
    """
    text = user_input.strip()
    if not text:
        return True
    # 极短消息（问候、回应等）
    if len(text) < 5:
        return True
    # 含任务关键词 → 走完整 runtime
    text_lower = text.lower()
    for kw in _TASK_KEYWORDS:
        if kw in text_lower:
            return False
    # 短消息无关键词 → 简单聊天
    if len(text) < 100:
        return True
    return False


__all__ = ["is_simple_conversation", "_TASK_KEYWORDS"]
