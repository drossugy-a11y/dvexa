"""Benchmark: Concurrent task isolation.

Verifies that multiple simultaneous submit_message() calls each produce
unique task_ids and independent emitters without exceptions.
"""

from __future__ import annotations

import time
import threading

from surface.chat.chat_runtime import ChatRuntime
from surface.chat.chat_dto import ChatResponseDTO


class _FakeKernelFast:
    """Fast kernel stub for concurrent testing."""

    def __init__(self) -> None:
        self.delay = 0.05

    def run_task(self, task_input: str) -> dict:
        import time
        if self.delay:
            time.sleep(self.delay)
        return {
            "status": "completed",
            "task_id": "test-concurrent",
            "goal": task_input[:60],
            "plan": ["step1"],
            "steps": [{"step_id": 1, "tool": "test", "output": "done"}],
            "result": "completed",
            "retry_count": 0,
        }


class TestConcurrentTasks:
    """Isolation benchmarks for concurrent task handling."""

    def test_three_quick_submissions(self) -> None:
        """Three quick submit_message calls should all return unique task_ids."""
        runtime = ChatRuntime(_FakeKernelFast())
        start = time.perf_counter()

        r1 = runtime.submit_message("task alpha")
        r2 = runtime.submit_message("task beta")
        r3 = runtime.submit_message("task gamma")

        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert isinstance(r1, ChatResponseDTO)
        assert isinstance(r2, ChatResponseDTO)
        assert isinstance(r3, ChatResponseDTO)
        assert r1.task_id != r2.task_id
        assert r2.task_id != r3.task_id
        assert r1.task_id != r3.task_id
        assert r1.status == "accepted"
        assert r2.status == "accepted"
        assert r3.status == "accepted"
        assert elapsed < 500, f"concurrent submissions too slow: {elapsed}ms"

    def test_unique_emitters_per_task(self) -> None:
        """Each submitted task should have its own emitter."""
        runtime = ChatRuntime(_FakeKernelFast())
        r1 = runtime.submit_message("task one")
        r2 = runtime.submit_message("task two")
        r3 = runtime.submit_message("task three")

        e1 = runtime.get_emitter(r1.task_id)
        e2 = runtime.get_emitter(r2.task_id)
        e3 = runtime.get_emitter(r3.task_id)

        assert e1 is not None
        assert e2 is not None
        assert e3 is not None
        assert e1.task_id != e2.task_id
        assert e2.task_id != e3.task_id

    def test_concurrent_from_threads(self) -> None:
        """Multiple threads submitting messages should not raise exceptions."""
        runtime = ChatRuntime(_FakeKernelFast())
        results: list[Exception | None] = []

        def submit(msg: str) -> None:
            try:
                runtime.submit_message(msg)
                results.append(None)
            except Exception as e:
                results.append(e)

        threads = [
            threading.Thread(target=submit, args=(f"thread-msg-{i}",))
            for i in range(5)
        ]

        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert all(r is None for r in results), f"concurrent errors: {[r for r in results if r]}"
        assert elapsed < 2000, f"concurrent threads too slow: {elapsed}ms"

    def test_emitter_independence(self) -> None:
        """Emitters from different tasks should not share state."""
        runtime = ChatRuntime(_FakeKernelFast())
        r1 = runtime.submit_message("task one")
        r2 = runtime.submit_message("task two")

        time.sleep(0.5)
        e1_events = runtime.get_task_events(r1.task_id)
        e2_events = runtime.get_task_events(r2.task_id)

        assert e1_events[0]["task_id"] == r1.task_id
        assert e2_events[0]["task_id"] == r2.task_id

    def test_active_task_tracking(self) -> None:
        """has_active_tasks and is_task_running should work correctly."""
        runtime = ChatRuntime(_FakeKernelFast())
        assert runtime.has_active_tasks() is False

        r1 = runtime.submit_message("task one")
        assert runtime.is_task_running(r1.task_id) is True
        assert runtime.has_active_tasks() is True

        r2 = runtime.submit_message("task two")
        assert runtime.is_task_running(r2.task_id) is True
        assert runtime.has_active_tasks() is True
