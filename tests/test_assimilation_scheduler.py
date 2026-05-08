"""Tests for Assimilation Scheduler v1.0 — 吞并节奏控制层"""

import os
import glob
import tempfile
import pytest

from governance.assimilation_scheduler import (
    AssimilationScheduler,
    AssimilationState,
    InvalidTransitionError,
    SchedulerBusyError,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def scheduler():
    """Fixture providing a scheduler with a temp devlog directory."""
    tmpdir = tempfile.mkdtemp()
    s = AssimilationScheduler()
    s.DEVLOG_DIR = tmpdir
    os.makedirs(tmpdir, exist_ok=True)
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TestStateMachine — basic state transitions
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateMachine:
    """Verify the basic READY → ANALYZING → TESTING → APPROVED → LOGGED → NEXT → READY flow."""

    def test_initial_state_is_ready(self, scheduler):
        assert scheduler.state == AssimilationState.READY

    def test_begin_transitions_to_analyzing(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        assert scheduler.state == AssimilationState.ANALYZING
        assert scheduler.current_module == "loader"

    def test_complete_analysis_transitions_to_testing(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        result = scheduler.complete_analysis(capabilities=["config_loader"])
        assert scheduler.state == AssimilationState.TESTING
        assert result["state"] == "testing"
        assert result["capabilities"] == ["config_loader"]

    def test_complete_testing_passed_transitions_to_approved(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.APPROVED

    def test_log_transitions_to_logged(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        result = scheduler.log()
        assert scheduler.state == AssimilationState.LOGGED
        assert result["status"] == "logged"

    def test_confirm_human_transitions_to_next(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        scheduler.log()
        result = scheduler.confirm_human()
        assert scheduler.state == AssimilationState.NEXT
        assert result["status"] == "confirmed"

    def test_next_round_returns_to_ready(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        scheduler.log()
        scheduler.confirm_human()
        result = scheduler.next_round()
        assert scheduler.state == AssimilationState.READY
        assert result["status"] == "ready_for_next"
        assert scheduler.round_count == 1

    def test_full_happy_path(self, scheduler):
        """README→ANALYZING→TESTING→APPROVED→LOGGED→NEXT→READY"""
        s = scheduler
        assert s.state == AssimilationState.READY

        s.begin("loader", risk_score=0.3)
        assert s.state == AssimilationState.ANALYZING
        assert s.current_module == "loader"

        s.complete_analysis(capabilities=["config_loader"])
        assert s.state == AssimilationState.TESTING

        s.complete_testing(passed=True)
        assert s.state == AssimilationState.APPROVED

        s.log()
        assert s.state == AssimilationState.LOGGED

        s.confirm_human()
        assert s.state == AssimilationState.NEXT

        s.next_round()
        assert s.state == AssimilationState.READY

    def test_cancel_from_any_state_returns_to_ready(self, scheduler):
        """Cancel should work from ANALYZING, TESTING, APPROVED, LOGGED, QUARANTINE, REJECTED."""
        s = scheduler

        # Cancel from ANALYZING
        s.begin("m1", risk_score=0.3)
        assert s.state == AssimilationState.ANALYZING
        result = s.cancel()
        assert s.state == AssimilationState.READY
        assert result["status"] == "cancelled"
        assert s.current_module is None

        # Cancel from TESTING
        s.begin("m2", risk_score=0.3)
        s.complete_analysis()
        assert s.state == AssimilationState.TESTING
        s.cancel()
        assert s.state == AssimilationState.READY

        # Cancel from APPROVED
        s.begin("m3", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.APPROVED
        s.cancel()
        assert s.state == AssimilationState.READY

        # Cancel from LOGGED
        s.begin("m4", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        assert s.state == AssimilationState.LOGGED
        s.cancel()
        assert s.state == AssimilationState.READY

        # Cancel from QUARANTINE
        s.begin("m5", risk_score=0.65)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.QUARANTINE
        s.cancel()
        assert s.state == AssimilationState.READY

        # Cancel from REJECTED
        s.begin("m6", risk_score=0.9)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.REJECTED
        s.cancel()
        assert s.state == AssimilationState.READY


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TestRiskThresholds — quarantine and reject
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskThresholds:
    """Verify risk_score thresholds: >= 0.6 → QUARANTINE, >= 0.7 → REJECT."""

    def test_risk_06_to_07_quarantines(self, scheduler):
        """risk=0.65 (between 0.6 and 0.7) should quarantine."""
        scheduler.begin("module", risk_score=0.65)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.QUARANTINE

    def test_risk_exactly_07_rejects(self, scheduler):
        """risk=0.7 is the new upper boundary — should reject (>= 0.7)."""
        scheduler.begin("module", risk_score=0.7)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.REJECTED

    def test_risk_above_08_rejects(self, scheduler):
        """risk=0.9 (> 0.8) should reject."""
        scheduler.begin("module", risk_score=0.9)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.REJECTED

    def test_risk_exactly_06_quarantines(self, scheduler):
        """risk=0.6 is the lower boundary — should quarantine (>= 0.6)."""
        scheduler.begin("module", risk_score=0.6)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.QUARANTINE

    def test_risk_exactly_08_rejects(self, scheduler):
        """risk=0.8 is the upper boundary — should reject (>= 0.8)."""
        scheduler.begin("module", risk_score=0.8)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.REJECTED

    def test_risk_below_06_allows_approval(self, scheduler):
        """risk=0.5 (< 0.6) should approve."""
        scheduler.begin("module", risk_score=0.5)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.APPROVED


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TestOneModuleAtATime — concurrency guard
# ═══════════════════════════════════════════════════════════════════════════════

class TestOneModuleAtATime:
    """Only one module can be assimilated at a time."""

    def test_begin_when_busy_raises_error(self, scheduler):
        scheduler.begin("module_a", risk_score=0.3)
        with pytest.raises(SchedulerBusyError):
            scheduler.begin("module_b", risk_score=0.2)

    def test_begin_allows_when_state_is_next(self, scheduler):
        """begin() should work when in NEXT state (is_busy=False for NEXT)."""
        s = scheduler
        s.begin("mod1", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        s.confirm_human()
        assert s.state == AssimilationState.NEXT
        # Should be allowed because NEXT is not "busy"
        result = s.begin("mod2", risk_score=0.2)
        assert result["status"] == "started"
        assert s.state == AssimilationState.ANALYZING
        assert s.current_module == "mod2"

    def test_begin_allows_when_state_is_ready(self, scheduler):
        result = scheduler.begin("module", risk_score=0.3)
        assert result["status"] == "started"
        assert scheduler.current_module == "module"

    def test_current_module_tracks_current_name(self, scheduler):
        assert scheduler.current_module is None
        scheduler.begin("tracker", risk_score=0.4)
        assert scheduler.current_module == "tracker"
        scheduler.cancel()
        assert scheduler.current_module is None

    def test_is_busy_property_true_when_not_ready_or_next(self, scheduler):
        s = scheduler
        assert not s.is_busy

        s.begin("m", risk_score=0.3)
        assert s.is_busy  # ANALYZING

        s.complete_analysis()
        assert s.is_busy  # TESTING

        s.complete_testing(passed=True)
        assert s.is_busy  # APPROVED

        s.log()
        assert s.is_busy  # LOGGED

    def test_is_busy_property_false_when_ready(self, scheduler):
        assert not scheduler.is_busy

    def test_is_busy_property_false_when_next(self, scheduler):
        s = scheduler
        s.begin("m", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        s.confirm_human()
        assert s.state == AssimilationState.NEXT
        assert not s.is_busy


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TestDevLogIntegration — DevLog writing
# ═══════════════════════════════════════════════════════════════════════════════

class TestDevLogIntegration:
    """Verify that the scheduler writes DevLog entries correctly."""

    def _get_devlog_files(self, scheduler):
        pattern = os.path.join(scheduler.DEVLOG_DIR, "*_assimilation_scheduler.md")
        return sorted(glob.glob(pattern))

    def _read_devlog(self, scheduler):
        files = self._get_devlog_files(scheduler)
        assert len(files) >= 1, "No devlog files found"
        with open(files[-1], "r", encoding="utf-8") as f:
            return f.read()

    def test_log_writes_to_devlog_directory(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        scheduler.log()
        files = self._get_devlog_files(scheduler)
        assert len(files) == 1

    def test_log_creates_markdown_entry(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        scheduler.log()
        content = self._read_devlog(scheduler)
        assert "# Assimilation Scheduler Log" in content
        assert "Assimilation Event: approved" in content

    def test_log_contains_required_fields(self, scheduler):
        scheduler.begin("loader", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        scheduler.log()
        content = self._read_devlog(scheduler)
        assert "**Timestamp**" in content
        assert "**Module**" in content
        assert "**Risk Score**" in content
        assert "**Result**" in content
        assert "**Reason**" in content
        assert "**Capabilities**" in content

    def test_rejected_also_writes_devlog(self, scheduler):
        scheduler.begin("module", risk_score=0.9)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.REJECTED
        content = self._read_devlog(scheduler)
        assert "Assimilation Event: rejected" in content

    def test_quarantine_also_writes_devlog(self, scheduler):
        scheduler.begin("module", risk_score=0.65)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.QUARANTINE
        content = self._read_devlog(scheduler)
        assert "Assimilation Event: quarantine" in content


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TestHumanConfirmation — human gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestHumanConfirmation:
    """Human must confirm before moving to the next round."""

    def test_confirm_human_before_log_raises_error(self, scheduler):
        scheduler.begin("module", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        assert scheduler.state == AssimilationState.APPROVED
        with pytest.raises(InvalidTransitionError):
            scheduler.confirm_human()

    def test_confirm_human_after_log_works(self, scheduler):
        scheduler.begin("module", risk_score=0.3)
        scheduler.complete_analysis()
        scheduler.complete_testing(passed=True)
        scheduler.log()
        assert scheduler.state == AssimilationState.LOGGED
        scheduler.confirm_human()
        assert scheduler.state == AssimilationState.NEXT

    def test_only_logged_allows_confirm_human(self, scheduler):
        """confirm_human must fail from any state other than LOGGED."""
        s = scheduler

        # READY
        with pytest.raises(InvalidTransitionError):
            s.confirm_human()

        # ANALYZING
        s.begin("m", risk_score=0.3)
        with pytest.raises(InvalidTransitionError):
            s.confirm_human()

        # TESTING
        s.complete_analysis()
        with pytest.raises(InvalidTransitionError):
            s.confirm_human()

        # APPROVED (tested above)
        s.complete_testing(passed=True)

        with pytest.raises(InvalidTransitionError):
            s.confirm_human()

        # LOGGED — should work
        s.log()
        s.confirm_human()
        assert s.state == AssimilationState.NEXT

    def test_next_round_requires_human_confirm(self, scheduler):
        """Cannot call next_round() without human confirm (must be in NEXT state)."""
        s = scheduler
        s.begin("module", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        assert s.state == AssimilationState.LOGGED
        # next_round requires NEXT state, but we're in LOGGED
        with pytest.raises(InvalidTransitionError):
            s.next_round()

    def test_quarantine_cannot_confirm_human(self, scheduler):
        """QUARANTINE modules cannot receive human confirm."""
        s = scheduler
        s.begin("module", risk_score=0.65)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.QUARANTINE
        with pytest.raises(InvalidTransitionError):
            s.confirm_human()

    def test_rejected_cannot_confirm_human(self, scheduler):
        """REJECTED modules cannot receive human confirm."""
        s = scheduler
        s.begin("module", risk_score=0.9)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.REJECTED
        with pytest.raises(InvalidTransitionError):
            s.confirm_human()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. TestHistoryAndStatus — audit trail
# ═══════════════════════════════════════════════════════════════════════════════

class TestHistoryAndStatus:
    """Verify the scheduler maintains a complete audit trail."""

    def test_history_records_all_attempts(self, scheduler):
        s = scheduler
        s.begin("module1", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        s.confirm_human()
        s.next_round()
        assert len(s.history()) == 1

        s.begin("module2", risk_score=0.5)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        s.confirm_human()
        s.next_round()
        assert len(s.history()) == 2

    def test_status_returns_current_state_and_module(self, scheduler):
        s = scheduler
        status = s.status()
        assert status["state"] == "ready"
        assert status["module"] is None
        assert status["is_busy"] is False

        s.begin("loader", risk_score=0.3)
        status = s.status()
        assert status["state"] == "analyzing"
        assert status["module"] == "loader"
        assert status["is_busy"] is True

    def test_history_includes_risk_score_and_result(self, scheduler):
        s = scheduler
        s.begin("module", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        s.confirm_human()
        s.next_round()

        h = s.history()
        assert len(h) == 1
        assert h[0]["module"] == "module"
        assert h[0]["risk_score"] == 0.3
        assert h[0]["result"] == "completed"
        assert "capabilities" in h[0]
        assert "timestamp" in h[0]

    def test_history_includes_cancelled_events(self, scheduler):
        s = scheduler
        s.begin("module", risk_score=0.3)
        s.complete_analysis()
        s.cancel()

        h = s.history()
        assert len(h) == 1
        assert h[0]["result"] == "cancelled"
        assert h[0]["module"] == "module"

    def test_history_includes_rejected_events(self, scheduler):
        s = scheduler
        s.begin("module", risk_score=0.9)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.REJECTED

        h = s.history()
        assert len(h) == 1
        assert h[0]["result"] == "rejected"
        assert h[0]["module"] == "module"
        assert h[0]["risk_score"] == 0.9

    def test_history_includes_quarantine_events(self, scheduler):
        s = scheduler
        s.begin("module", risk_score=0.65)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.QUARANTINE

        h = s.history()
        assert len(h) == 1
        assert h[0]["result"] == "quarantine"
        assert h[0]["risk_score"] == 0.65

    def test_multiple_rounds_all_recorded(self, scheduler):
        s = scheduler
        modules = ["mod_a", "mod_b", "mod_c"]
        for mod in modules:
            s.begin(mod, risk_score=0.3)
            s.complete_analysis()
            s.complete_testing(passed=True)
            s.log()
            s.confirm_human()
            s.next_round()

        assert len(s.history()) == 3
        assert s.round_count == 3
        for i, mod in enumerate(modules):
            assert s.history()[i]["module"] == mod
            assert s.history()[i]["result"] == "completed"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. TestEdgeCases — edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and error handling."""

    def test_begin_with_empty_name(self, scheduler):
        with pytest.raises(ValueError, match="module_name must not be empty"):
            scheduler.begin("")

    def test_begin_with_whitespace_name(self, scheduler):
        with pytest.raises(ValueError, match="module_name must not be empty"):
            scheduler.begin("   ")

    def test_begin_with_negative_risk(self, scheduler):
        """Negative risk should be clamped to 0.0."""
        result = scheduler.begin("module", risk_score=-0.5)
        assert result["risk_score"] == 0.0

    def test_begin_with_risk_over_1(self, scheduler):
        """Risk > 1.0 should be clamped to 1.0."""
        result = scheduler.begin("module", risk_score=1.5)
        assert result["risk_score"] == 1.0

    def test_begin_with_risk_exactly_1(self, scheduler):
        """Risk = 1.0 should be allowed (boundary)."""
        result = scheduler.begin("module", risk_score=1.0)
        assert result["risk_score"] == 1.0

    def test_begin_with_risk_exactly_0(self, scheduler):
        """Risk = 0.0 should be allowed (boundary)."""
        result = scheduler.begin("module", risk_score=0.0)
        assert result["risk_score"] == 0.0

    def test_invalid_transition_raises_error(self, scheduler):
        """Cannot call complete_analysis from READY."""
        with pytest.raises(InvalidTransitionError):
            scheduler.complete_analysis()

    def test_complete_testing_from_wrong_state(self, scheduler):
        """Cannot call complete_testing from READY."""
        with pytest.raises(InvalidTransitionError):
            scheduler.complete_testing(passed=True)

    def test_double_log_raises_error(self, scheduler):
        s = scheduler
        s.begin("module", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        assert s.state == AssimilationState.LOGGED
        # Cannot log() from LOGGED
        with pytest.raises(InvalidTransitionError):
            s.log()

    def test_double_confirm_raises_error(self, scheduler):
        s = scheduler
        s.begin("module", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        s.log()
        s.confirm_human()
        assert s.state == AssimilationState.NEXT
        # Cannot confirm_human from NEXT
        with pytest.raises(InvalidTransitionError):
            s.confirm_human()

    def test_cancel_when_idempotent(self, scheduler):
        """cancel() from READY should return success, not error."""
        s = scheduler
        assert s.state == AssimilationState.READY
        result = s.cancel()
        assert result["status"] == "already_ready"
        assert s.state == AssimilationState.READY

    def test_cancel_twice_keeps_ready(self, scheduler):
        s = scheduler
        s.cancel()
        s.cancel()
        assert s.state == AssimilationState.READY

    def test_return_values_contain_required_keys(self, scheduler):
        """All public methods should return dicts with status key."""
        s = scheduler

        r1 = s.begin("m", risk_score=0.3)
        assert "status" in r1 and "state" in r1

        r2 = s.complete_analysis(capabilities=["c1"])
        assert "status" in r2 and "state" in r2

        r3 = s.complete_testing(passed=True)
        assert "status" in r3 and "state" in r3

        r4 = s.log()
        assert "status" in r4 and "state" in r4

        r5 = s.confirm_human()
        assert "status" in r5 and "state" in r5

        s.next_round()
        r6 = s.cancel()
        assert "status" in r6 and "state" in r6

    def test_previously_rejected_module_can_restart(self, scheduler):
        """A module that was rejected should be restartable after cancel."""
        s = scheduler
        s.begin("module", risk_score=0.9)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.REJECTED

        s.cancel()
        assert s.state == AssimilationState.READY

        # Now try again with lower risk
        s.begin("module", risk_score=0.3)
        s.complete_analysis()
        s.complete_testing(passed=True)
        assert s.state == AssimilationState.APPROVED
