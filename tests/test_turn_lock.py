"""Tests for Turn Lock v1 — 轮次锁定系统"""

import pytest
import time
from runtime.turn_lock import TurnLock, TurnState


class TestTurnLock:

    def setup_method(self):
        self.lock = TurnLock()

    def test_initial_state(self):
        assert self.lock.state == TurnState.IDLE
        assert self.lock.can_start_turn()
        assert not self.lock.is_locked()
        assert self.lock.turn_count == 0

    def test_start_turn_changes_state(self):
        record = self.lock.start_turn("hello")
        assert self.lock.state == TurnState.ACTIVE
        assert self.lock.is_locked()
        assert not self.lock.can_start_turn()
        assert record.user_input == "hello"
        assert record.turn_id.startswith("turn-")

    def test_cannot_start_twice(self):
        self.lock.start_turn("first")
        with pytest.raises(RuntimeError, match="TURN_LOCK"):
            self.lock.start_turn("second")

    def test_mark_streaming(self):
        self.lock.start_turn("test")
        self.lock.mark_streaming()
        assert self.lock.state == TurnState.STREAMING
        assert self.lock.is_locked()

    def test_cannot_mark_streaming_from_idle(self):
        with pytest.raises(RuntimeError, match="TURN_LOCK"):
            self.lock.mark_streaming()

    def test_complete_turn_resets(self):
        self.lock.start_turn("hello")
        record = self.lock.complete_turn("world")
        assert self.lock.state == TurnState.IDLE
        assert self.lock.can_start_turn()
        assert not self.lock.is_locked()
        assert record.assistant_output == "world"
        assert record.duration() >= 0

    def test_cannot_complete_from_idle(self):
        with pytest.raises(RuntimeError, match="TURN_LOCK"):
            self.lock.complete_turn()

    def test_turn_count(self):
        self.lock.start_turn("a")
        self.lock.complete_turn("A")
        self.lock.start_turn("b")
        self.lock.complete_turn("B")
        assert self.lock.turn_count == 2

    def test_get_history(self):
        self.lock.start_turn("hello")
        self.lock.complete_turn("world")
        history = self.lock.get_history()
        assert len(history) == 1
        assert history[0]["user_input"] == "hello"
        assert history[0]["has_output"] is True

    def test_reset_recovers(self):
        self.lock.start_turn("stuck")
        self.lock.reset()
        assert self.lock.state == TurnState.IDLE
        assert self.lock.can_start_turn()

    def test_complete_from_streaming(self):
        self.lock.start_turn("hello")
        self.lock.mark_streaming()
        record = self.lock.complete_turn("world")
        assert record.assistant_output == "world"

    def test_turn_record_duration(self):
        self.lock.start_turn("slow")
        time.sleep(0.05)
        record = self.lock.complete_turn("done")
        assert record.duration() >= 0.04

    def test_is_locked_during_streaming(self):
        self.lock.start_turn("test")
        assert self.lock.is_locked()
        self.lock.mark_streaming()
        assert self.lock.is_locked()
        self.lock.complete_turn("done")
        assert not self.lock.is_locked()
