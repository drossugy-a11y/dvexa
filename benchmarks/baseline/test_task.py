"""Benchmark: Task routing and mode escalation.

Tests that task inputs route to full runtime pipeline and that
RuntimeMode detection correctly escalates complex chat to TASK mode.
"""

from __future__ import annotations

import time

from governance.system_directive_engine import (
    _classify_intent,
    RuntimeMode,
    SystemDirectiveEngine,
    _estimate_complexity,
)


class TestTaskRoutingBaseline:
    """Baseline benchmarks for task routing and mode detection."""

    def test_task_keyword_classifies_as_task(self) -> None:
        """Input with 'implement' should be classified as TASK."""
        start = time.perf_counter()
        mode = _classify_intent("implement a login system")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert mode == RuntimeMode.TASK
        assert elapsed < 10, f"task classification too slow: {elapsed}ms"

    def test_chinese_task_classifies_as_task(self) -> None:
        """Chinese task keywords should classify as TASK."""
        start = time.perf_counter()
        mode = _classify_intent("构建一个Web应用")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert mode == RuntimeMode.TASK
        assert elapsed < 10, f"chinese task too slow: {elapsed}ms"

    def test_greeting_classifies_as_chat(self) -> None:
        """Simple greeting should be classified as CHAT."""
        start = time.perf_counter()
        mode = _classify_intent("你好")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert mode == RuntimeMode.CHAT
        assert elapsed < 10, f"greeting classification too slow: {elapsed}ms"

    def test_complex_chat_escalates_to_task(self) -> None:
        """Complex chat (complexity > 0.6) should escalate to TASK mode."""
        start = time.perf_counter()
        engine = SystemDirectiveEngine()
        directive = engine.process("给我写一份完整的商业计划书", {
            "complexity": 0.8,
            "has_history": True,
        })
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert directive.mode == RuntimeMode.TASK
        assert directive.must_plan is True
        assert directive.must_stream is True
        assert elapsed < 10, f"mode escalation too slow: {elapsed}ms"

    def test_simple_chat_stays_chat(self) -> None:
        """Simple chat with low complexity should stay CHAT mode."""
        start = time.perf_counter()
        engine = SystemDirectiveEngine()
        directive = engine.process("你好吗？", {
            "complexity": 0.1,
        })
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert directive.mode == RuntimeMode.CHAT
        assert directive.must_plan is False
        assert elapsed < 10, f"simple chat too slow: {elapsed}ms"

    def test_tool_keyword_classifies_as_tool(self) -> None:
        """Input with 'fix' keyword should be classified as TOOL."""
        start = time.perf_counter()
        mode = _classify_intent("修复这个bug")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert mode == RuntimeMode.TOOL
        assert elapsed < 10, f"tool classification too slow: {elapsed}ms"

    def test_explore_keyword_classifies_as_explore(self) -> None:
        """Input with 'analyze' keyword should be classified as EXPLORE."""
        start = time.perf_counter()
        mode = _classify_intent("分析一下这个数据集的分布")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert mode == RuntimeMode.EXPLORE
        assert elapsed < 10, f"explore classification too slow: {elapsed}ms"

    def test_system_query_classifies_as_system(self) -> None:
        """System-prefixed input should be classified as SYSTEM."""
        start = time.perf_counter()
        mode = _classify_intent("system: status")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert mode == RuntimeMode.SYSTEM
        assert elapsed < 10, f"system classification too slow: {elapsed}ms"

    def test_complexity_estimation(self) -> None:
        """Complexity estimation should return a value between 0 and 1."""
        start = time.perf_counter()
        score = _estimate_complexity(
            "This is a multi-step comprehensive pipeline that requires full end-to-end processing"
        )
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert 0.0 <= score <= 1.0
        assert score >= 0.5, f"expected high complexity, got {score}"
        assert elapsed < 10, f"complexity estimation too slow: {elapsed}ms"

    def test_short_input_has_low_complexity(self) -> None:
        """Short input without complexity keywords should have low complexity."""
        start = time.perf_counter()
        score = _estimate_complexity("你好")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert score < 0.5, f"expected low complexity, got {score}"
        assert elapsed < 10, f"low complexity estimation too slow: {elapsed}ms"
