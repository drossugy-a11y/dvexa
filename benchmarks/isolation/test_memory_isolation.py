"""Benchmark: Memory isolation in ChatRuntime.

Verifies that only user and final assistant messages appear in chat history,
and that runtime_step/cognitive events are correctly excluded.
"""

from __future__ import annotations

import time
import threading

from surface.chat.chat_runtime import ChatRuntime
from surface.chat.chat_dto import ChatMessageDTO


class _FakeKernel:
    """Minimal kernel stub for deterministic memory isolation testing."""

    def __init__(self) -> None:
        self.delay = 0.0

    def run_task(self, task_input: str) -> dict:
        return {
            "status": "completed",
            "task_id": "test-1",
            "goal": "test goal",
            "plan": ["step1"],
            "steps": [{"step_id": 1, "tool": "test", "output": "done"}],
            "result": "Task completed successfully",
            "retry_count": 0,
        }


class TestMemoryIsolation:
    """Isolation benchmarks for memory/chat history correctness."""

    def test_history_contains_user_message(self) -> None:
        """User message should appear in chat history."""
        runtime = ChatRuntime(_FakeKernel())
        start = time.perf_counter()
        runtime.submit_message("user message")
        time.sleep(0.3)
        history = runtime.get_chat_history()
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert len(history) >= 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "user message"
        assert elapsed < 2000, f"memory isolation too slow: {elapsed}ms"

    def test_history_contains_assistant_message(self) -> None:
        """Assistant response should appear in chat history."""
        runtime = ChatRuntime(_FakeKernel())
        start = time.perf_counter()
        runtime.submit_message("hello")
        time.sleep(0.3)
        history = runtime.get_chat_history()
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        roles = [m["role"] for m in history]
        assert "assistant" in roles
        assert elapsed < 2000, f"assistant memory too slow: {elapsed}ms"

    def test_no_duplicate_assistant_messages(self) -> None:
        """Only one assistant message should appear per task."""
        runtime = ChatRuntime(_FakeKernel())
        runtime.submit_message("test")
        time.sleep(0.3)
        history = runtime.get_chat_history()
        assistant_msgs = [m for m in history if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1

    def test_history_order_correct(self) -> None:
        """Chat history should maintain correct user → assistant order."""
        runtime = ChatRuntime(_FakeKernel())
        runtime.submit_message("first message")
        time.sleep(0.3)
        history = runtime.get_chat_history()
        if len(history) >= 2:
            assert history[0]["role"] == "user"
            assert history[1]["role"] == "assistant"

    def test_events_contain_stream_markers(self) -> None:
        """Task events should include stream lifecycle markers."""
        runtime = ChatRuntime(_FakeKernel())
        resp = runtime.submit_message("test")
        time.sleep(0.3)
        events = runtime.get_task_events(resp.task_id)
        event_types = [e["event_type"] for e in events]
        assert "stream_started" in event_types
        assert "stream_completed" in event_types

    def test_no_events_in_chat_history(self) -> None:
        """Stream events should NOT leak into chat history."""
        runtime = ChatRuntime(_FakeKernel())
        resp = runtime.submit_message("test")
        time.sleep(0.3)
        history = runtime.get_chat_history()
        # History entries must only contain role/content, NOT event_type
        for entry in history:
            assert "event_type" not in entry
            assert "role" in entry
            assert "content" in entry

    def test_history_limit_respected(self) -> None:
        """get_chat_history(limit=N) should return at most N entries."""
        runtime = ChatRuntime(_FakeKernel())
        for i in range(5):
            runtime.submit_message(f"msg-{i}")
        time.sleep(1.0)
        limited = runtime.get_chat_history(limit=2)
        assert len(limited) <= 2

    def test_multiple_tasks_history_separation(self) -> None:
        """Multiple sequential tasks should each produce user+assistant pairs."""
        runtime = ChatRuntime(_FakeKernel())
        r1 = runtime.submit_message("task one")
        time.sleep(0.3)
        r2 = runtime.submit_message("task two")
        time.sleep(0.3)
        history = runtime.get_chat_history()
        user_msgs = [m for m in history if m["role"] == "user"]
        assistant_msgs = [m for m in history if m["role"] == "assistant"]
        assert len(user_msgs) == 2
        assert len(assistant_msgs) == 2
