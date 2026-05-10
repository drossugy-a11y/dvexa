"""Benchmark: State machine recovery after crash.

Verifies that the RuntimeStateMachine correctly returns to IDLE
and releases the TurnLock after a simulated crash during execution.
"""

from __future__ import annotations

import time

from runtime.runtime_state_machine import RuntimeStateMachine, RuntimeState
from runtime.turn_lock import TurnLock, TurnState


class TestStateRecovery:
    """Resilience benchmarks for state machine recovery."""

    def test_state_machine_returns_to_idle_after_error(self) -> None:
        """State machine should return to IDLE after ERROR → RECOVERY → IDLE."""
        sm = RuntimeStateMachine()
        start = time.perf_counter()

        sm.start_turn()
        sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        sm.transition(RuntimeState.GOVERNANCE_CHECK)
        sm.transition(RuntimeState.PLANNING)
        sm.transition(RuntimeState.EXECUTING)

        # Simulate crash: transition to ERROR
        sm.mark_error("simulated crash")

        # Recover
        sm.mark_recovery()
        sm.complete_turn()

        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert sm.is_idle is True
        assert sm.get_state() == RuntimeState.IDLE
        assert elapsed < 100, f"state recovery too slow: {elapsed}ms"

    def test_turnlock_releases_after_crash_simulation(self) -> None:
        """TurnLock should release (IDLE) after a simulated crash and reset."""
        lock = TurnLock()
        start = time.perf_counter()

        lock.start_turn("crash simulation")
        assert lock.state != TurnState.IDLE
        assert lock.is_locked() is True

        # Force reset (crash recovery path)
        lock.reset()

        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert lock.state == TurnState.IDLE
        assert lock.is_locked() is False
        assert lock.can_start_turn() is True
        assert elapsed < 100, f"lock release too slow: {elapsed}ms"

    def test_recovery_from_deep_execution(self) -> None:
        """State machine should recover from deep in the execution chain."""
        sm = RuntimeStateMachine()
        sm.start_turn()
        sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        sm.transition(RuntimeState.GOVERNANCE_CHECK)
        sm.transition(RuntimeState.PLANNING)
        sm.transition(RuntimeState.EXECUTING)
        sm.transition(RuntimeState.TOOL_RUNNING)
        sm.transition(RuntimeState.EXECUTING)
        sm.transition(RuntimeState.STREAMING)

        # Crash from STREAMING
        start = time.perf_counter()
        sm.mark_error("deep crash")
        sm.mark_recovery()
        sm.complete_turn()
        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert sm.is_idle is True
        assert sm.get_state() == RuntimeState.IDLE
        assert elapsed < 100, f"deep recovery too slow: {elapsed}ms"

    def test_state_transition_history(self) -> None:
        """State machine should record all transitions including error/recovery."""
        sm = RuntimeStateMachine()
        sm.start_turn()
        sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        sm.transition(RuntimeState.GOVERNANCE_CHECK)
        sm.transition(RuntimeState.PLANNING)
        sm.transition(RuntimeState.EXECUTING)
        sm.mark_error("test error")
        sm.mark_recovery()
        sm.complete_turn()

        assert len(sm.history) >= 7
        states = [(e.from_state.value, e.to_state.value) for e in sm.history]
        assert ("idle", "input_received") in states
        assert any(
            e.to_state == RuntimeState.RECOVERY for e in sm.history
        )

    def test_rollback_after_crash(self) -> None:
        """State machine rollback should work after error state."""
        sm = RuntimeStateMachine()
        sm.start_turn()
        sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        sm.transition(RuntimeState.GOVERNANCE_CHECK)
        sm.transition(RuntimeState.PLANNING)
        sm.transition(RuntimeState.EXECUTING)
        sm.mark_error("crash during execution")

        start = time.perf_counter()
        event = sm.rollback()
        elapsed = round((time.perf_counter() - start) * 1000, 3)

        assert event is not None
        assert sm.is_idle is True or sm.get_state() != RuntimeState.ERROR
        assert elapsed < 100, f"rollback too slow: {elapsed}ms"

    def test_turnlock_after_state_machine_recovery(self) -> None:
        """Both state machine and turn lock should be consistent after recovery."""
        sm = RuntimeStateMachine()
        lock = TurnLock()

        sm.start_turn()
        sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        sm.transition(RuntimeState.GOVERNANCE_CHECK)
        sm.transition(RuntimeState.PLANNING)
        sm.transition(RuntimeState.EXECUTING)
        lock.start_turn("coordinated task")

        # Crash both
        sm.mark_error("coordinated crash")
        lock.reset()

        # Recovery
        sm.mark_recovery()
        sm.complete_turn()

        assert sm.is_idle is True
        assert lock.state == TurnState.IDLE
        assert lock.can_start_turn() is True

    def test_idle_after_complete_turn(self) -> None:
        """State machine should be IDLE after normal complete_turn."""
        sm = RuntimeStateMachine()
        sm.start_turn()
        sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        sm.transition(RuntimeState.GOVERNANCE_CHECK)
        sm.transition(RuntimeState.PLANNING)
        sm.transition(RuntimeState.EXECUTING)
        sm.transition(RuntimeState.MEMORY_COMMIT)
        sm.transition(RuntimeState.COMPLETED)
        sm.complete_turn()

        assert sm.is_idle is True
        assert sm.get_state() == RuntimeState.IDLE
