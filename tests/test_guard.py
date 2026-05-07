"""CBF (Control Boundary Filter) 测试 — v1.6

测试范围：
  - sanitize：正确剥离禁止字段
  - assert_signal：正确拦截/放行信号
  - verify：检测清洗状态
"""

import pytest
from core.guard import CBF, ControlSignal


class TestCBFSanitize:
    def test_allows_step_id_and_output(self):
        result = CBF.sanitize({"step_id": 1, "output": "hello"})
        assert result == {"step_id": 1, "output": "hello"}

    def test_removes_confidence(self):
        result = CBF.sanitize({"step_id": 1, "output": "done", "confidence": 0.9})
        assert "confidence" not in result

    def test_removes_score(self):
        result = CBF.sanitize({"step_id": 1, "output": "done", "score": 85})
        assert "score" not in result

    def test_removes_risk(self):
        result = CBF.sanitize({"step_id": 1, "output": "done", "risk": "HIGH"})
        assert "risk" not in result

    def test_removes_validation(self):
        result = CBF.sanitize({"step_id": 1, "output": "done", "validation": {"ok": True}})
        assert "validation" not in result

    def test_removes_status(self):
        result = CBF.sanitize({"step_id": 1, "output": "done", "status": "success"})
        assert "status" not in result

    def test_removes_tool_metadata(self):
        result = CBF.sanitize({"step_id": 1, "output": "done", "tool": "llm"})
        assert "tool" not in result

    def test_removes_all_banned_fields(self):
        result = CBF.sanitize({
            "step_id": 1,
            "output": "done",
            "confidence": 0.9,
            "score": 85,
            "risk": "LOW",
            "validation": {"ok": True},
            "suggestion": "try again",
            "status": "success",
            "tool": "llm",
        })
        assert result == {"step_id": 1, "output": "done"}

    def test_empty_result_returns_empty(self):
        result = CBF.sanitize({})
        assert result == {}

    def test_unknown_fields_are_removed(self):
        result = CBF.sanitize({"step_id": 1, "output": "x", "random_field": "y"})
        assert "random_field" not in result


class TestCBFAssertSignal:
    def test_legal_signal_passes(self):
        CBF.assert_signal("step_completed")  # should not raise

    def test_all_control_signals_are_valid(self):
        for signal in ControlSignal:
            CBF.assert_signal(signal.value)

    def test_banned_signal_raises(self):
        with pytest.raises(ValueError, match="禁止信号"):
            CBF.assert_signal("confidence")

    def test_unknown_signal_raises(self):
        with pytest.raises(ValueError):
            CBF.assert_signal("nonexistent")


class TestCBFVerify:
    def test_clean_result_passes(self):
        CBF.verify({"step_id": 1, "output": "ok"})

    def test_dirty_result_raises(self):
        with pytest.raises(AssertionError, match="未清洗"):
            CBF.verify({"step_id": 1, "output": "ok", "confidence": 0.9})


class TestControlSignal:
    def test_all_signals_defined(self):
        expected = {
            "step_completed",
            "step_failed",
            "retry_exceeded",
            "plan_ready",
            "execution_result",
        }
        actual = {s.value for s in ControlSignal}
        assert actual == expected
