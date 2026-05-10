"""Memory Gate v1 — 记忆写入守卫

防止 assistant 中间输出泄漏到 prompt 上下文。

规则:
  ALLOW:
    - user messages
    - final assistant messages

  DENY:
    - stream chunks
    - partial outputs
    - intermediate reasoning steps
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class MemoryAction(str, Enum):
    STORE = "store"
    DISCARD = "discard"


_MEMORY_GATE_COUNTER = {"discarded": 0, "stored": 0}


def _classify_for_memory(role: str, event_type: str = "",
                         is_final: bool = False) -> MemoryAction:
    """判断消息是否允许进入记忆。"""
    # Stream chunks: always discard
    if event_type in ("message_chunk", "stream_chunk", "stream_started",
                      "stream_completed", "stream_error"):
        return MemoryAction.DISCARD

    if event_type in ("tool_execution", "planning_started",
                      "governance_decision", "memory_hit"):
        return MemoryAction.DISCARD

    # Partial assistant: discard
    if role in ("assistant", "assistant_partial", "stream_chunk") and not is_final:
        return MemoryAction.DISCARD

    # User input: store
    if role == "user":
        return MemoryAction.STORE

    # Final assistant: store
    if role in ("assistant", "assistant_final") and is_final:
        return MemoryAction.STORE

    if event_type in ("execution_complete",) and is_final:
        return MemoryAction.STORE

    return MemoryAction.DISCARD


def should_store(role: str, event_type: str = "",
                 is_final: bool = False) -> bool:
    """外部接口: 是否允许存入记忆。"""
    return _classify_for_memory(role, event_type, is_final) == MemoryAction.STORE


def commit_to_memory(message: dict,
                     store_fn: Any = None) -> MemoryAction:
    """Memory Gate 主入口。

    Args:
        message: 消息 dict (必须含 role, 可选 event_type, is_final)
        store_fn: 可选的存储回调。为 None 时只判断。

    Returns:
        MemoryAction.STORE 或 DISCARD
    """
    role = message.get("role", "")
    event_type = message.get("event_type", "")
    is_final = message.get("is_final", False)

    action = _classify_for_memory(role, event_type, is_final)

    if action == MemoryAction.DISCARD:
        _MEMORY_GATE_COUNTER["discarded"] += 1
        return MemoryAction.DISCARD

    if store_fn is not None:
        try:
            store_fn(message)
        except Exception:
            return MemoryAction.DISCARD

    _MEMORY_GATE_COUNTER["stored"] += 1
    return MemoryAction.STORE


def gate_stats() -> dict:
    """获取 gate 统计信息。"""
    return dict(_MEMORY_GATE_COUNTER)


def reset_stats() -> None:
    """重置统计。"""
    _MEMORY_GATE_COUNTER["discarded"] = 0
    _MEMORY_GATE_COUNTER["stored"] = 0
