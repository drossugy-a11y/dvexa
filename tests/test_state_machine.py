"""Tests for RuntimeStateMachine — full coverage of all transitions.

Covers:
  1. Initial state            (3 tests)
  2. All allowed transitions  (22 tests)
  3. Forbidden transitions    (13 tests)
  4. mark_error               (3 tests)
  5. reset                    (2 tests)
  6. Observer                 (2 tests)
  7. start_turn/complete_turn (2 tests)
  ─────────────────────────────
  Total: 47 tests
"""

import pytest

from runtime.runtime_state_machine import (
    RuntimeState,
    RuntimeStateMachine,
)


class TestRuntimeStateMachine:
    """Comprehensive test suite for RuntimeStateMachine."""

    def setup_method(self) -> None:
        self.sm = RuntimeStateMachine()

    # ═══════════════════════════════════════════════════════════════════
    # 1. Initial state
    # ═══════════════════════════════════════════════════════════════════

    def test_initial_state_is_idle(self) -> None:
        assert self.sm.get_state() == RuntimeState.IDLE

    def test_is_idle_returns_true_initially(self) -> None:
        assert self.sm.is_idle is True

    def test_is_running_returns_false_initially(self) -> None:
        assert self.sm.is_running is False

    # ═══════════════════════════════════════════════════════════════════
    # 2. All allowed transitions (22 total — every edge in _TRANSITIONS)
    # ═══════════════════════════════════════════════════════════════════

    # -- Forward execution path --
    def test_idle_to_input_received(self) -> None:
        self.sm.start_turn("t1")
        assert self.sm.get_state() == RuntimeState.INPUT_RECEIVED

    def test_input_received_to_directive_evaluation(self) -> None:
        self.sm.start_turn()
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        assert self.sm.get_state() == RuntimeState.DIRECTIVE_EVALUATION

    def test_directive_evaluation_to_governance_check(self) -> None:
        self._walk_to(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        assert self.sm.get_state() == RuntimeState.GOVERNANCE_CHECK

    def test_governance_check_to_planning(self) -> None:
        self._walk_to(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.PLANNING)
        assert self.sm.get_state() == RuntimeState.PLANNING

    def test_governance_check_to_blocked(self) -> None:
        self._walk_to(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.BLOCKED)
        assert self.sm.get_state() == RuntimeState.BLOCKED

    def test_blocked_to_idle(self) -> None:
        self._walk_to(RuntimeState.BLOCKED)
        self.sm.transition(RuntimeState.IDLE)
        assert self.sm.get_state() == RuntimeState.IDLE

    def test_planning_to_executing(self) -> None:
        self._walk_to(RuntimeState.PLANNING)
        self.sm.transition(RuntimeState.EXECUTING)
        assert self.sm.get_state() == RuntimeState.EXECUTING

    def test_executing_to_tool_running(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        self.sm.transition(RuntimeState.TOOL_RUNNING)
        assert self.sm.get_state() == RuntimeState.TOOL_RUNNING

    def test_tool_running_to_executing(self) -> None:
        self._walk_to(RuntimeState.TOOL_RUNNING)
        self.sm.transition(RuntimeState.EXECUTING)
        assert self.sm.get_state() == RuntimeState.EXECUTING

    def test_executing_to_streaming(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        self.sm.transition(RuntimeState.STREAMING)
        assert self.sm.get_state() == RuntimeState.STREAMING

    def test_streaming_to_memory_commit(self) -> None:
        self._walk_to(RuntimeState.STREAMING)
        self.sm.transition(RuntimeState.MEMORY_COMMIT)
        assert self.sm.get_state() == RuntimeState.MEMORY_COMMIT

    def test_executing_to_memory_commit(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        self.sm.transition(RuntimeState.MEMORY_COMMIT)
        assert self.sm.get_state() == RuntimeState.MEMORY_COMMIT

    def test_memory_commit_to_completed(self) -> None:
        self._walk_to(RuntimeState.MEMORY_COMMIT)
        self.sm.transition(RuntimeState.COMPLETED)
        assert self.sm.get_state() == RuntimeState.COMPLETED

    def test_completed_to_idle(self) -> None:
        self._walk_to(RuntimeState.COMPLETED)
        self.sm.transition(RuntimeState.IDLE)
        assert self.sm.get_state() == RuntimeState.IDLE

    # -- Error and recovery paths --
    def test_executing_to_error(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        self.sm.mark_error("exec failure")
        assert self.sm.get_state() == RuntimeState.ERROR

    def test_tool_running_to_error(self) -> None:
        self._walk_to(RuntimeState.TOOL_RUNNING)
        self.sm.transition(RuntimeState.ERROR)
        assert self.sm.get_state() == RuntimeState.ERROR

    def test_streaming_to_error(self) -> None:
        self._walk_to(RuntimeState.STREAMING)
        self.sm.transition(RuntimeState.ERROR)
        assert self.sm.get_state() == RuntimeState.ERROR

    def test_memory_commit_to_error(self) -> None:
        self._walk_to(RuntimeState.MEMORY_COMMIT)
        self.sm.transition(RuntimeState.ERROR)
        assert self.sm.get_state() == RuntimeState.ERROR

    def test_error_to_recovery(self) -> None:
        self._walk_to(RuntimeState.ERROR)
        self.sm.transition(RuntimeState.RECOVERY)
        assert self.sm.get_state() == RuntimeState.RECOVERY

    def test_error_to_idle(self) -> None:
        self._walk_to(RuntimeState.ERROR)
        self.sm.transition(RuntimeState.IDLE)
        assert self.sm.get_state() == RuntimeState.IDLE

    def test_recovery_to_idle(self) -> None:
        self._walk_to(RuntimeState.RECOVERY)
        self.sm.transition(RuntimeState.IDLE)
        assert self.sm.get_state() == RuntimeState.IDLE

    def test_recovery_to_error(self) -> None:
        self._walk_to(RuntimeState.RECOVERY)
        self.sm.transition(RuntimeState.ERROR)
        assert self.sm.get_state() == RuntimeState.ERROR

    # ═══════════════════════════════════════════════════════════════════
    # 3. Forbidden transitions (13 tests)
    # ═══════════════════════════════════════════════════════════════════

    def test_cannot_skip_idle_to_planning(self) -> None:
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.PLANNING)

    def test_cannot_skip_idle_to_executing(self) -> None:
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.EXECUTING)

    def test_cannot_skip_idle_to_completed(self) -> None:
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.COMPLETED)

    def test_cannot_skip_idle_to_governance_check(self) -> None:
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.GOVERNANCE_CHECK)

    def test_cannot_skip_input_received_to_completed(self) -> None:
        self.sm.start_turn()
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.COMPLETED)

    def test_cannot_skip_planning_to_completed(self) -> None:
        self._walk_to(RuntimeState.PLANNING)
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.COMPLETED)

    def test_cannot_transition_executing_to_idle(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.IDLE)

    def test_cannot_transition_executing_to_planning(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.PLANNING)

    def test_cannot_transition_executing_to_directive_evaluation(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)

    def test_cannot_transition_completed_to_executing(self) -> None:
        self._walk_to(RuntimeState.COMPLETED)
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.EXECUTING)

    def test_cannot_transition_error_to_planning(self) -> None:
        self._walk_to(RuntimeState.ERROR)
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.PLANNING)

    def test_cannot_transition_error_to_executing(self) -> None:
        self._walk_to(RuntimeState.ERROR)
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.EXECUTING)

    def test_cannot_transition_blocked_to_planning(self) -> None:
        self._walk_to(RuntimeState.BLOCKED)
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.PLANNING)

    # ═══════════════════════════════════════════════════════════════════
    # 4. mark_error
    # ═══════════════════════════════════════════════════════════════════

    def test_mark_error_from_executing(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        ev = self.sm.mark_error("something broke")
        assert self.sm.get_state() == RuntimeState.ERROR
        assert ev.metadata.get("reason") == "something broke"
        assert ev.from_state == RuntimeState.EXECUTING
        assert ev.to_state == RuntimeState.ERROR

    def test_mark_error_sets_state_to_error(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        self.sm.mark_error()
        assert self.sm.get_state() == RuntimeState.ERROR

    def test_mark_error_twice_still_works(self) -> None:
        self._walk_to(RuntimeState.EXECUTING)
        self.sm.mark_error("first")
        self.sm.transition(RuntimeState.IDLE)
        self._walk_to(RuntimeState.EXECUTING)
        self.sm.mark_error("second")
        assert self.sm.get_state() == RuntimeState.ERROR

    # ═══════════════════════════════════════════════════════════════════
    # 5. reset (via IDLE transition)
    # ═══════════════════════════════════════════════════════════════════

    def test_reset_from_error_returns_to_idle(self) -> None:
        self._walk_to(RuntimeState.ERROR)
        ev = self.sm.transition(RuntimeState.IDLE)
        assert self.sm.get_state() == RuntimeState.IDLE
        assert self.sm.is_idle is True
        assert ev.from_state == RuntimeState.ERROR
        assert ev.to_state == RuntimeState.IDLE

    def test_reset_from_completed_returns_to_idle(self) -> None:
        self._walk_to(RuntimeState.COMPLETED)
        ev = self.sm.complete_turn()
        assert self.sm.get_state() == RuntimeState.IDLE
        assert ev.from_state == RuntimeState.COMPLETED
        assert ev.to_state == RuntimeState.IDLE

    # ═══════════════════════════════════════════════════════════════════
    # 6. Observer
    # ═══════════════════════════════════════════════════════════════════

    def test_observer_fires_on_transition(self) -> None:
        events = []
        self.sm.subscribe(lambda e: events.append(e))
        self.sm.start_turn("t1")
        assert len(events) == 1

    def test_observer_receives_correct_event_data(self) -> None:
        events = []
        self.sm.subscribe(lambda e: events.append(e))
        self.sm.start_turn("turn-x")
        ev = events[0]
        assert ev.from_state == RuntimeState.IDLE
        assert ev.to_state == RuntimeState.INPUT_RECEIVED
        assert ev.turn_id == "turn-x"
        assert isinstance(ev.timestamp, float)
        assert ev.timestamp > 0

    # ═══════════════════════════════════════════════════════════════════
    # 7. start_turn / complete_turn
    # ═══════════════════════════════════════════════════════════════════

    def test_start_turn_sets_turn_id_and_state(self) -> None:
        ev = self.sm.start_turn("turn-42")
        assert self.sm.get_state() == RuntimeState.INPUT_RECEIVED
        assert self.sm.turn_id == "turn-42"
        assert ev.turn_id == "turn-42"

    def test_complete_turn_resets_to_idle(self) -> None:
        self._walk_to(RuntimeState.COMPLETED)
        ev = self.sm.complete_turn()
        assert self.sm.get_state() == RuntimeState.IDLE
        assert ev.metadata.get("turn_complete") is True

    # ═══════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════

    def _walk_to(self, target: RuntimeState) -> None:
        """Walk the state machine from IDLE to *target* via valid transitions only."""
        _PATHS = {
            RuntimeState.INPUT_RECEIVED: [
                lambda: self.sm.start_turn("walk"),
            ],
            RuntimeState.DIRECTIVE_EVALUATION: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
            ],
            RuntimeState.GOVERNANCE_CHECK: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
            ],
            RuntimeState.PLANNING: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.PLANNING),
            ],
            RuntimeState.EXECUTING: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.PLANNING),
                lambda: self.sm.transition(RuntimeState.EXECUTING),
            ],
            RuntimeState.TOOL_RUNNING: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.PLANNING),
                lambda: self.sm.transition(RuntimeState.EXECUTING),
                lambda: self.sm.transition(RuntimeState.TOOL_RUNNING),
            ],
            RuntimeState.STREAMING: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.PLANNING),
                lambda: self.sm.transition(RuntimeState.EXECUTING),
                lambda: self.sm.transition(RuntimeState.STREAMING),
            ],
            RuntimeState.MEMORY_COMMIT: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.PLANNING),
                lambda: self.sm.transition(RuntimeState.EXECUTING),
                lambda: self.sm.transition(RuntimeState.MEMORY_COMMIT),
            ],
            RuntimeState.COMPLETED: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.PLANNING),
                lambda: self.sm.transition(RuntimeState.EXECUTING),
                lambda: self.sm.transition(RuntimeState.MEMORY_COMMIT),
                lambda: self.sm.transition(RuntimeState.COMPLETED),
            ],
            RuntimeState.BLOCKED: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.BLOCKED),
            ],
            RuntimeState.ERROR: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.PLANNING),
                lambda: self.sm.transition(RuntimeState.EXECUTING),
                lambda: self.sm.mark_error("walk error"),
            ],
            RuntimeState.RECOVERY: [
                lambda: self.sm.start_turn("walk"),
                lambda: self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION),
                lambda: self.sm.transition(RuntimeState.GOVERNANCE_CHECK),
                lambda: self.sm.transition(RuntimeState.PLANNING),
                lambda: self.sm.transition(RuntimeState.EXECUTING),
                lambda: self.sm.mark_error("walk error"),
                lambda: self.sm.transition(RuntimeState.RECOVERY),
            ],
        }
        for step in _PATHS[target]:
            step()
