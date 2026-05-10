"""Tests for Stream Guard v1 — 消息分类 + 传播阻断"""

import pytest
from runtime.stream_guard import (
    classify_message, MessageType,
    should_trigger_llm, should_store_memory,
    should_block_reentry, is_stream_content,
    assert_no_reentry,
)


class TestClassifyMessage:

    def test_user_input(self):
        assert classify_message("user") == MessageType.USER_INPUT

    def test_assistant_final(self):
        assert classify_message("assistant", is_final=True) == MessageType.ASSISTANT_FINAL
        assert classify_message("assistant", "execution_complete") == MessageType.ASSISTANT_FINAL
        assert classify_message("assistant", "stream_completed") == MessageType.ASSISTANT_FINAL

    def test_assistant_partial(self):
        assert classify_message("assistant") == MessageType.ASSISTANT_PARTIAL
        assert classify_message("assistant_partial") == MessageType.ASSISTANT_PARTIAL

    def test_stream_chunk(self):
        assert classify_message("stream_chunk") == MessageType.STREAM_CHUNK
        assert classify_message("", "message_chunk") == MessageType.STREAM_CHUNK
        assert classify_message("", "tool_execution") == MessageType.STREAM_CHUNK
        assert classify_message("", "planning_started") == MessageType.STREAM_CHUNK

    def test_system_event(self):
        assert classify_message("system") == MessageType.SYSTEM_EVENT


class TestStreamGuardRules:

    def test_should_trigger_llm_only_user(self):
        assert should_trigger_llm(MessageType.USER_INPUT) is True
        assert should_trigger_llm(MessageType.ASSISTANT_FINAL) is False
        assert should_trigger_llm(MessageType.STREAM_CHUNK) is False
        assert should_trigger_llm(MessageType.ASSISTANT_PARTIAL) is False

    def test_should_store_memory_only_final(self):
        assert should_store_memory(MessageType.USER_INPUT) is True
        assert should_store_memory(MessageType.ASSISTANT_FINAL) is True
        assert should_store_memory(MessageType.STREAM_CHUNK) is False
        assert should_store_memory(MessageType.ASSISTANT_PARTIAL) is False

    def test_should_block_reentry(self):
        assert should_block_reentry(MessageType.STREAM_CHUNK) is True
        assert should_block_reentry(MessageType.ASSISTANT_PARTIAL) is True
        assert should_block_reentry(MessageType.USER_INPUT) is False
        assert should_block_reentry(MessageType.ASSISTANT_FINAL) is False

    def test_is_stream_content(self):
        assert is_stream_content(MessageType.STREAM_CHUNK) is True
        assert is_stream_content(MessageType.USER_INPUT) is False
        assert is_stream_content(MessageType.ASSISTANT_FINAL) is False


class TestAssertNoReentry:

    def test_user_input_allowed(self):
        assert_no_reentry("user")  # must not raise

    def test_assistant_final_allowed(self):
        assert_no_reentry("assistant", "execution_complete")  # must not raise

    def test_stream_chunk_blocked(self):
        with pytest.raises(RuntimeError, match="REENTRY BLOCKED"):
            assert_no_reentry("stream_chunk")

    def test_assistant_partial_blocked(self):
        with pytest.raises(RuntimeError, match="REENTRY BLOCKED"):
            assert_no_reentry("assistant_partial")
