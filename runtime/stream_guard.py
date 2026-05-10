"""Stream Guard v1 — 消息分类 + 传播阻断

职责:
  - 分类消息类型 (USER_INPUT / ASSISTANT_FINAL / STREAM_CHUNK / SYSTEM_EVENT)
  - 阻断非法传播路径

规则:
  - STREAM_CHUNK → UI only (NO MEMORY, NO PROMPT)
  - ASSISTANT_FINAL → memory only
  - USER_INPUT → triggers LLM
  - SYSTEM_EVENT → governance only
"""

from __future__ import annotations

from enum import Enum


class MessageType(str, Enum):
    USER_INPUT = "user_input"
    ASSISTANT_FINAL = "assistant_final"
    ASSISTANT_PARTIAL = "assistant_partial"
    STREAM_CHUNK = "stream_chunk"
    SYSTEM_EVENT = "system_event"


def classify_message(role: str, event_type: str = "",
                     is_final: bool = False) -> MessageType:
    """确定性消息类型分类。"""
    if role == "system" or event_type in ("system_event", "governance_event"):
        return MessageType.SYSTEM_EVENT

    if role == "user":
        return MessageType.USER_INPUT

    if role in ("assistant", "assistant_final", "assistant_partial"):
        if is_final or event_type in ("execution_complete", "stream_completed"):
            return MessageType.ASSISTANT_FINAL
        if role == "assistant_partial":
            return MessageType.ASSISTANT_PARTIAL
        return MessageType.ASSISTANT_PARTIAL

    if event_type == "stream_chunk" or role == "stream_chunk":
        return MessageType.STREAM_CHUNK

    if event_type in ("message_chunk", "tool_execution", "planning_started",
                      "governance_decision", "memory_hit", "stream_started"):
        return MessageType.STREAM_CHUNK

    return MessageType.STREAM_CHUNK


def should_trigger_llm(message_type: MessageType) -> bool:
    """是否触发新一轮 LLM 推理。"""
    return message_type == MessageType.USER_INPUT


def should_store_memory(message_type: MessageType) -> bool:
    """是否存入记忆。"""
    return message_type in (MessageType.USER_INPUT, MessageType.ASSISTANT_FINAL)


def should_block_reentry(message_type: MessageType) -> bool:
    """是否阻断重新进入 prompt/LLM 管道。"""
    return message_type in (MessageType.STREAM_CHUNK,
                            MessageType.ASSISTANT_PARTIAL)


def is_stream_content(message_type: MessageType) -> bool:
    """是否仅为流式 UI 内容。"""
    return message_type == MessageType.STREAM_CHUNK


def assert_no_reentry(role: str, event_type: str = "") -> None:
    """全局不变式: assistant 输出永不回流到 LLM 输入。"""
    msg_type = classify_message(role, event_type)
    if should_block_reentry(msg_type):
        raise RuntimeError(
            f"REENTRY BLOCKED: {msg_type.value} (role={role}, event={event_type}) "
            f"cannot enter LLM input pipeline"
        )
