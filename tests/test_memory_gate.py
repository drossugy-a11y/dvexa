"""Tests for Memory Gate v1 — 记忆写入守卫"""

from memory.memory_gate import (
    should_store, commit_to_memory, MemoryAction,
    gate_stats, reset_stats,
)


class TestMemoryGate:

    def setup_method(self):
        reset_stats()

    def test_user_message_should_store(self):
        assert should_store("user") is True

    def test_assistant_final_should_store(self):
        assert should_store("assistant", is_final=True) is True
        assert should_store("assistant_final", is_final=True) is True

    def test_stream_chunk_should_discard(self):
        assert should_store("", "message_chunk") is False
        assert should_store("stream_chunk") is False

    def test_assistant_partial_should_discard(self):
        assert should_store("assistant") is False
        assert should_store("assistant_partial") is False

    def test_tool_event_should_discard(self):
        assert should_store("", "tool_execution") is False
        assert should_store("", "planning_started") is False
        assert should_store("", "governance_decision") is False

    def test_commit_discards_stream_chunk(self):
        result = commit_to_memory({"role": "", "event_type": "message_chunk"})
        assert result == MemoryAction.DISCARD

    def test_commit_stores_user(self):
        stored = []

        def store_fn(msg):
            stored.append(msg)

        result = commit_to_memory(
            {"role": "user", "content": "hello"}, store_fn
        )
        assert result == MemoryAction.STORE
        assert len(stored) == 1

    def test_commit_stores_assistant_final(self):
        stored = []

        def store_fn(msg):
            stored.append(msg)

        result = commit_to_memory(
            {"role": "assistant", "content": "world", "is_final": True}, store_fn
        )
        assert result == MemoryAction.STORE
        assert len(stored) == 1

    def test_commit_stores_execution_complete(self):
        stored = []

        def store_fn(msg):
            stored.append(msg)

        result = commit_to_memory(
            {"role": "assistant", "event_type": "execution_complete", "is_final": True}, store_fn
        )
        assert result == MemoryAction.STORE
        assert len(stored) == 1

    def test_gate_stats(self):
        commit_to_memory({"role": "user", "content": "hi"}, lambda _: None)
        commit_to_memory({"role": "", "event_type": "message_chunk"})
        stats = gate_stats()
        assert stats["stored"] >= 1
        assert stats["discarded"] >= 1

    def test_reset_stats(self):
        commit_to_memory({"role": "", "event_type": "message_chunk"})
        reset_stats()
        stats = gate_stats()
        assert stats["stored"] == 0
        assert stats["discarded"] == 0

    def test_store_fn_exception_does_not_crash(self):
        def broken_fn(msg):
            raise ValueError("storage error")

        result = commit_to_memory(
            {"role": "user", "content": "hi"}, broken_fn
        )
        assert result == MemoryAction.DISCARD
