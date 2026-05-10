"""Tests for RuntimeStateMachine v1 — 统一运行时状态机"""

import pytest
from runtime.runtime_state_machine import (
    RuntimeStateMachine, RuntimeState, StateTransitionEvent,
)


class TestRuntimeStateMachine:

    def setup_method(self):
        self.sm = RuntimeStateMachine()

    # ── 初始状态 ──────────────────────────────────────────────────────

    def test_initial_state(self):
        assert self.sm.get_state() == RuntimeState.IDLE
        assert self.sm.is_idle
        assert not self.sm.is_running

    # ── 有效转换 ──────────────────────────────────────────────────────

    def test_valid_transition_idle_to_input(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        assert self.sm.get_state() == RuntimeState.INPUT_RECEIVED

    def test_full_execution_path(self):
        path = [
            RuntimeState.INPUT_RECEIVED,
            RuntimeState.DIRECTIVE_EVALUATION,
            RuntimeState.GOVERNANCE_CHECK,
            RuntimeState.PLANNING,
            RuntimeState.EXECUTING,
            RuntimeState.STREAMING,
            RuntimeState.MEMORY_COMMIT,
            RuntimeState.COMPLETED,
            RuntimeState.IDLE,
        ]
        for state in path:
            self.sm.transition(state)
        assert self.sm.get_state() == RuntimeState.IDLE

    def test_tool_execution_path(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.PLANNING)
        self.sm.transition(RuntimeState.EXECUTING)
        self.sm.transition(RuntimeState.TOOL_RUNNING)
        assert self.sm.get_state() == RuntimeState.TOOL_RUNNING
        self.sm.transition(RuntimeState.EXECUTING)
        assert self.sm.get_state() == RuntimeState.EXECUTING

    def test_governance_blocked_path(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.BLOCKED)
        assert self.sm.get_state() == RuntimeState.BLOCKED
        self.sm.transition(RuntimeState.IDLE)
        assert self.sm.is_idle

    def test_error_recovery_path(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.PLANNING)
        self.sm.transition(RuntimeState.EXECUTING)
        self.sm.transition(RuntimeState.ERROR)
        assert self.sm.get_state() == RuntimeState.ERROR
        self.sm.transition(RuntimeState.RECOVERY)
        assert self.sm.get_state() == RuntimeState.RECOVERY
        self.sm.transition(RuntimeState.IDLE)
        assert self.sm.is_idle

    def test_can_transition(self):
        assert self.sm.can_transition(RuntimeState.INPUT_RECEIVED)
        assert not self.sm.can_transition(RuntimeState.PLANNING)
        assert not self.sm.can_transition(RuntimeState.COMPLETED)
        assert not self.sm.can_transition(RuntimeState.ERROR)

    # ── 无效转换 ──────────────────────────────────────────────────────

    def test_invalid_transition_raises(self):
        with pytest.raises(RuntimeError, match="INVALID STATE TRANSITION"):
            self.sm.transition(RuntimeState.COMPLETED)

    def test_idle_to_planning_invalid(self):
        with pytest.raises(RuntimeError):
            self.sm.transition(RuntimeState.PLANNING)

    def test_governance_to_streaming_invalid(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        with pytest.raises(RuntimeError):
            self.sm.transition(RuntimeState.STREAMING)

    # ── 便捷方法 ──────────────────────────────────────────────────────

    def test_start_turn(self):
        event = self.sm.start_turn("turn-123")
        assert self.sm.get_state() == RuntimeState.INPUT_RECEIVED
        assert event.to_state == RuntimeState.INPUT_RECEIVED
        assert event.turn_id == "turn-123"

    def test_complete_turn(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.PLANNING)
        self.sm.transition(RuntimeState.EXECUTING)
        self.sm.transition(RuntimeState.STREAMING)
        self.sm.transition(RuntimeState.MEMORY_COMMIT)
        self.sm.transition(RuntimeState.COMPLETED)
        self.sm.complete_turn()
        assert self.sm.is_idle

    def test_mark_blocked(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self.sm.mark_blocked("policy violation")
        assert self.sm.get_state() == RuntimeState.BLOCKED

    def test_mark_error_and_recovery(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.PLANNING)
        self.sm.transition(RuntimeState.EXECUTING)
        self.sm.mark_error("execution failed")
        assert self.sm.get_state() == RuntimeState.ERROR
        self.sm.mark_recovery()
        assert self.sm.get_state() == RuntimeState.RECOVERY

    # ── 事件发射 ──────────────────────────────────────────────────────

    def test_transition_returns_event(self):
        event = self.sm.transition(RuntimeState.INPUT_RECEIVED)
        assert isinstance(event, StateTransitionEvent)
        assert event.from_state == RuntimeState.IDLE
        assert event.to_state == RuntimeState.INPUT_RECEIVED
        assert event.timestamp > 0

    def test_event_to_dict(self):
        event = self.sm.transition(RuntimeState.INPUT_RECEIVED)
        d = event.to_dict()
        assert d["from"] == "idle"
        assert d["to"] == "input_received"

    # ── 历史 ──────────────────────────────────────────────────────────

    def test_history_order(self):
        for state in [RuntimeState.INPUT_RECEIVED, RuntimeState.DIRECTIVE_EVALUATION]:
            self.sm.transition(state)
        assert len(self.sm.history) == 2
        assert self.sm.history[0].to_state == RuntimeState.INPUT_RECEIVED
        assert self.sm.history[1].to_state == RuntimeState.DIRECTIVE_EVALUATION

    def test_rollback(self):
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        event = self.sm.rollback()
        assert event is not None
        assert event.metadata.get("rollback") is True

    def test_cannot_rollback_with_short_history(self):
        with pytest.raises(RuntimeError, match="CANNOT ROLLBACK"):
            self.sm.rollback()

    # ── 观察者 ────────────────────────────────────────────────────────

    def test_observer_notified(self):
        received = []

        def obs(event):
            received.append(event)

        self.sm.subscribe(obs)
        self.sm.transition(RuntimeState.INPUT_RECEIVED)

        assert len(received) == 1
        assert received[0].to_state == RuntimeState.INPUT_RECEIVED

    def test_unsubscribe(self):
        received = []

        def obs(event):
            received.append(event)

        self.sm.subscribe(obs)
        self.sm.unsubscribe(obs)
        self.sm.transition(RuntimeState.INPUT_RECEIVED)

        assert len(received) == 0

    # ── to_dict ───────────────────────────────────────────────────────

    def test_to_dict(self):
        self.sm.start_turn("t1")
        d = self.sm.to_dict()
        assert d["current_state"] == "input_received"
        assert d["turn_id"] == "t1"
        assert d["transition_count"] == 1
        assert not d["is_idle"]
        assert d["uptime"] >= 0
        assert d["last_transition"]["from"] == "idle"

    # ── is_running ────────────────────────────────────────────────────

    def test_is_running_states(self):
        assert not self.sm.is_running
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        assert self.sm.is_running
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        assert self.sm.is_running

    def test_is_not_running_terminal_states(self):
        # ERROR
        self.sm.transition(RuntimeState.INPUT_RECEIVED)
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.PLANNING)
        self.sm.transition(RuntimeState.EXECUTING)
        self.sm.transition(RuntimeState.ERROR)
        assert not self.sm.is_running

    # ── 并发安全 ──────────────────────────────────────────────────────

    def test_concurrent_transitions_blocked(self):
        import threading
        errors = []

        def try_bad_transition():
            try:
                self.sm.transition(RuntimeState.COMPLETED)
            except RuntimeError as e:
                errors.append(str(e))

        threads = [threading.Thread(target=try_bad_transition) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 5

    # ── 完整流式生命周期 ──────────────────────────────────────────────

    def test_stream_lifecycle(self):
        """EXECUTING → STREAMING → MEMORY_COMMIT → COMPLETED → IDLE"""
        self.sm.start_turn()
        self.sm.transition(RuntimeState.DIRECTIVE_EVALUATION)
        self.sm.transition(RuntimeState.GOVERNANCE_CHECK)
        self.sm.transition(RuntimeState.PLANNING)
        self.sm.transition(RuntimeState.EXECUTING)
        self.sm.transition(RuntimeState.STREAMING)
        self.sm.transition(RuntimeState.MEMORY_COMMIT)
        self.sm.transition(RuntimeState.COMPLETED)
        self.sm.transition(RuntimeState.IDLE)
        assert self.sm.get_state() == RuntimeState.IDLE
