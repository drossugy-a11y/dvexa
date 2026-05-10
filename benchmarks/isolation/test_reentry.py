"""Benchmark: Reentry prevention enforcement.

Verifies that Stream Guard correctly blocks reentry attempts for
assistant_partial, stream_chunk, and system_event message types,
while allowing user messages through.
"""

from __future__ import annotations

import time
import pytest

from runtime.stream_guard import (
    assert_no_reentry,
    classify_message,
    should_block_reentry,
    should_trigger_llm,
    MessageType,
)


class TestReentryPrevention:
    """Isolation benchmarks for reentry prevention."""

    def test_assistant_partial_raises(self) -> None:
        """assistant_partial role should raise RuntimeError."""
        start = time.perf_counter()
        with pytest.raises(RuntimeError, match="REENTRY BLOCKED"):
            assert_no_reentry("assistant_partial")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"reentry block too slow: {elapsed}ms"

    def test_stream_chunk_raises(self) -> None:
        """stream_chunk role should raise RuntimeError."""
        start = time.perf_counter()
        with pytest.raises(RuntimeError, match="REENTRY BLOCKED"):
            assert_no_reentry("stream_chunk")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"stream chunk block too slow: {elapsed}ms"

    def test_system_event_does_not_raise(self) -> None:
        """system role should NOT raise RuntimeError (system events are logged, not blocked)."""
        start = time.perf_counter()
        assert_no_reentry("system")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"system event allow too slow: {elapsed}ms"

    def test_governance_event_does_not_raise(self) -> None:
        """governance_event type should NOT raise RuntimeError."""
        start = time.perf_counter()
        assert_no_reentry("assistant", "governance_event")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"governance event allow too slow: {elapsed}ms"

    def test_user_does_not_raise(self) -> None:
        """User input should NOT raise RuntimeError."""
        start = time.perf_counter()
        # Should complete without exception
        assert_no_reentry("user")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"user allow too slow: {elapsed}ms"

    def test_assistant_final_does_not_raise(self) -> None:
        """Assistant final message should NOT raise RuntimeError."""
        start = time.perf_counter()
        assert_no_reentry("assistant", "execution_complete")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"assistant final allow too slow: {elapsed}ms"

    def test_classify_message_types(self) -> None:
        """Message classification should correctly identify each type."""
        start = time.perf_counter()
        assert classify_message("user") == MessageType.USER_INPUT
        assert classify_message("assistant", "execution_complete") == MessageType.ASSISTANT_FINAL
        assert classify_message("assistant_partial") == MessageType.ASSISTANT_PARTIAL
        assert classify_message("stream_chunk") == MessageType.STREAM_CHUNK
        assert classify_message("system") == MessageType.SYSTEM_EVENT
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"classification too slow: {elapsed}ms"

    def test_should_block_reentry_correctness(self) -> None:
        """should_block_reentry should block correct types."""
        start = time.perf_counter()
        assert should_block_reentry(MessageType.STREAM_CHUNK) is True
        assert should_block_reentry(MessageType.ASSISTANT_PARTIAL) is True
        assert should_block_reentry(MessageType.USER_INPUT) is False
        assert should_block_reentry(MessageType.ASSISTANT_FINAL) is False
        assert should_block_reentry(MessageType.SYSTEM_EVENT) is False
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"block check too slow: {elapsed}ms"

    def test_should_trigger_llm_only_user(self) -> None:
        """Only USER_INPUT should trigger LLM."""
        start = time.perf_counter()
        assert should_trigger_llm(MessageType.USER_INPUT) is True
        assert should_trigger_llm(MessageType.ASSISTANT_FINAL) is False
        assert should_trigger_llm(MessageType.STREAM_CHUNK) is False
        assert should_trigger_llm(MessageType.SYSTEM_EVENT) is False
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 10, f"LLM trigger check too slow: {elapsed}ms"
