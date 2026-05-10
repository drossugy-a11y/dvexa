"""Benchmark: Simple chat routing detection.

Measures latency and correctness of is_simple_conversation() from
runtime.runtime_router under various input patterns.
"""

from __future__ import annotations

import time

from runtime.runtime_router import is_simple_conversation


class TestSimpleChatBaseline:
    """Baseline benchmarks for simple conversation detection."""

    def test_greeting_returns_true(self) -> None:
        """Greetings should be classified as simple chat."""
        start = time.perf_counter()
        result = is_simple_conversation("你好")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is True
        # latency benchmark annotation
        assert elapsed < 10, f"greeting classification too slow: {elapsed}ms"

    def test_short_question_returns_true(self) -> None:
        """Short questions should be classified as simple chat."""
        start = time.perf_counter()
        result = is_simple_conversation("今天天气怎么样")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is True
        assert elapsed < 10, f"short question classification too slow: {elapsed}ms"

    def test_english_greeting_returns_true(self) -> None:
        """English greetings should be classified as simple chat."""
        start = time.perf_counter()
        result = is_simple_conversation("hello")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is True
        assert elapsed < 10, f"english greeting too slow: {elapsed}ms"

    def test_simple_yes_returns_true(self) -> None:
        """Short affirmative should be classified as simple chat."""
        start = time.perf_counter()
        result = is_simple_conversation("yes")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is True
        assert elapsed < 10, f"simple yes too slow: {elapsed}ms"

    def test_task_keyword_returns_false(self) -> None:
        """Messages containing task keywords should route to full runtime."""
        start = time.perf_counter()
        result = is_simple_conversation("实现一个量化回测系统")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is False
        assert elapsed < 10, f"task keyword detection too slow: {elapsed}ms"

    def test_code_request_returns_false(self) -> None:
        """Code requests should route to full runtime."""
        start = time.perf_counter()
        result = is_simple_conversation("实现一个量化回测系统")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is False
        assert elapsed < 10, f"code request too slow: {elapsed}ms"

    def test_english_task_returns_false(self) -> None:
        """English task requests should route to full runtime."""
        start = time.perf_counter()
        result = is_simple_conversation("create a new project")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is False
        assert elapsed < 10, f"english task too slow: {elapsed}ms"

    def test_empty_input_returns_true(self) -> None:
        """Empty input should be classified as simple chat."""
        start = time.perf_counter()
        result = is_simple_conversation("")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is True
        assert elapsed < 10, f"empty input too slow: {elapsed}ms"

    def test_long_pure_question_returns_true(self) -> None:
        """Long pure questions (no task keywords) should route to simple chat."""
        start = time.perf_counter()
        long_q = "请问你对人工智能在医疗领域的应用有什么看法"
        result = is_simple_conversation(long_q)
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is True
        assert elapsed < 10, f"long question too slow: {elapsed}ms"

    def test_mixed_chat_and_task_returns_false(self) -> None:
        """Mixed chat with task keywords should route to full runtime."""
        start = time.perf_counter()
        result = is_simple_conversation("你好，帮我分析一下这个项目")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert result is False
        assert elapsed < 10, f"mixed input too slow: {elapsed}ms"
