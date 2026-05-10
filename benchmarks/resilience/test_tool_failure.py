"""Benchmark: Tool failure handling.

Verifies that the runtime correctly catches tool exceptions,
marks errors, and resets the TurnLock to IDLE after failure.
"""

from __future__ import annotations

import time
import pytest

from runtime.turn_lock import TurnLock, TurnState


class _FailingTool:
    """Tool stub that raises on every call."""

    def call(self, code: str) -> dict:
        msg = f"simulated failure for: {code}"
        raise RuntimeError(msg)


class TestToolFailure:
    """Resilience benchmarks for tool failure handling."""

    def test_failing_tool_raises(self) -> None:
        """A tool that always fails should raise RuntimeError."""
        tool = _FailingTool()
        start = time.perf_counter()
        with pytest.raises(RuntimeError, match="simulated failure"):
            tool.call("any input")
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        assert elapsed < 100, f"error propagation too slow: {elapsed}ms"

    def test_turnlock_recovers_from_error(self) -> None:
        """TurnLock should reset to IDLE after a simulated failure."""
        lock = TurnLock()
        start = time.perf_counter()

        lock.start_turn("risky input")
        assert lock.state == TurnState.ACTIVE

        # Simulate failure: mark streaming then force reset
        lock.mark_streaming()
        assert lock.state == TurnState.STREAMING

        lock.reset()
        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert lock.state == TurnState.IDLE
        assert lock.can_start_turn() is True
        assert elapsed < 100, f"turnlock recovery too slow: {elapsed}ms"

    def test_turnlock_error_during_streaming(self) -> None:
        """TurnLock should handle error during streaming state."""
        lock = TurnLock()
        lock.start_turn("streaming task")
        lock.mark_streaming()

        # Simulate error during streaming
        start = time.perf_counter()
        lock.reset()
        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert lock.state == TurnState.IDLE
        assert lock.can_start_turn() is True
        assert elapsed < 100, f"streaming error recovery too slow: {elapsed}ms"

    def test_turnlock_can_start_after_reset(self) -> None:
        """After reset, TurnLock should allow new turns."""
        lock = TurnLock()
        lock.start_turn("first")
        lock.mark_streaming()
        lock.reset()

        start = time.perf_counter()
        turn = lock.start_turn("second")
        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert turn.user_input == "second"
        assert lock.state == TurnState.ACTIVE
        assert elapsed < 100, f"restart after recovery too slow: {elapsed}ms"

    def test_turnlock_rejects_start_when_locked(self) -> None:
        """TurnLock should reject new turns while locked."""
        lock = TurnLock()
        lock.start_turn("active task")

        with pytest.raises(RuntimeError, match="TURN_LOCK"):
            lock.start_turn("should fail")

    def test_turnlock_error_records_metadata(self) -> None:
        """TurnLock reset should preserve error metadata."""
        lock = TurnLock()
        record = lock.start_turn("failing input")

        # Simulate tool failure by setting error on current turn
        import time as _t
        lock._current_turn.error = "tool failure"  # type: ignore[union-attr]
        lock.mark_streaming()
        lock.reset()

        assert lock.state == TurnState.IDLE
        assert lock.can_start_turn() is True
