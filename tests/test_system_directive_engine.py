"""Tests for SystemDirectiveEngine — 确定性行为控制"""

from __future__ import annotations

from governance.system_directive_engine import (
    SystemDirectiveEngine, SystemDirective, RuntimeMode,
    _classify_intent, _estimate_complexity,
)


class TestIntentClassifier:

    def test_chat_intent(self):
        assert _classify_intent("hello") == RuntimeMode.CHAT
        assert _classify_intent("hi there") == RuntimeMode.CHAT
        assert _classify_intent("what's up") == RuntimeMode.CHAT

    def test_task_intent(self):
        assert _classify_intent("how to build a web app") == RuntimeMode.TASK
        assert _classify_intent("create a login system") == RuntimeMode.TASK
        assert _classify_intent("implement user authentication") == RuntimeMode.TASK
        assert _classify_intent("重构这个模块") == RuntimeMode.TASK

    def test_tool_intent(self):
        assert _classify_intent("fix this bug") == RuntimeMode.TOOL
        assert _classify_intent("debug the error") == RuntimeMode.TOOL
        assert _classify_intent("run the test suite") == RuntimeMode.TOOL
        assert _classify_intent("修复这个错误") == RuntimeMode.TOOL

    def test_explore_intent(self):
        assert _classify_intent("analyze this codebase") == RuntimeMode.EXPLORE
        assert _classify_intent("research the architecture") == RuntimeMode.EXPLORE
        assert _classify_intent("explain how this works") == RuntimeMode.EXPLORE

    def test_system_intent(self):
        assert _classify_intent("system: check status") == RuntimeMode.SYSTEM
        assert _classify_intent("/help") == RuntimeMode.SYSTEM
        assert _classify_intent("status") == RuntimeMode.SYSTEM

    def test_system_context_override(self):
        assert _classify_intent("hello", {"system_query": True}) == RuntimeMode.SYSTEM


class TestComplexityEstimator:

    def test_low_complexity(self):
        assert _estimate_complexity("hello") < 0.3
        assert _estimate_complexity("hi") < 0.3

    def test_medium_complexity(self):
        score = _estimate_complexity("write a complete authentication system")
        assert 0.1 <= score <= 0.7

    def test_high_complexity(self):
        long_text = "implement a full pipeline " * 30
        score = _estimate_complexity(long_text)
        assert score >= 0.2

    def test_context_bumps_complexity(self):
        base = _estimate_complexity("build project")
        with_history = _estimate_complexity("build project", {"has_history": True})
        assert with_history >= base


class TestSystemDirectiveEngine:

    def setup_method(self):
        self.engine = SystemDirectiveEngine()

    def test_chat_mode_default(self):
        directive = self.engine.process("hello")
        assert directive.mode == RuntimeMode.CHAT
        assert not directive.must_plan
        assert not directive.must_use_tools
        assert not directive.must_stream
        assert directive.reasoning_level == "light"

    def test_task_mode_requires_plan(self):
        directive = self.engine.process("how to build a web application")
        assert directive.mode == RuntimeMode.TASK
        assert directive.must_plan
        assert directive.must_stream
        assert directive.reasoning_level == "deep"

    def test_tool_mode_requires_tools(self):
        directive = self.engine.process("fix this bug")
        assert directive.mode == RuntimeMode.TOOL
        assert directive.must_plan
        assert directive.must_use_tools
        assert directive.must_stream

    def test_explore_mode_deep_reasoning(self):
        directive = self.engine.process("analyze this codebase")
        assert directive.mode == RuntimeMode.EXPLORE
        assert directive.reasoning_level == "full"
        assert not directive.must_plan

    def test_system_mode_full_constraints(self):
        directive = self.engine.process("system: check status")
        assert directive.mode == RuntimeMode.SYSTEM
        assert directive.must_plan
        assert directive.must_use_tools
        assert directive.reasoning_level == "full"

    def test_complexity_escalates_to_task(self):
        directive = self.engine.process("hello", {"complexity": 0.8})
        assert directive.mode == RuntimeMode.TASK

    def test_degraded_governance_enforces_strict(self):
        directive = self.engine.process(
            "hello", {"governance_degraded": True, "complexity": 0.1}
        )
        assert directive.governance_level == "strict"

    def test_complexity_overrides_reasoning(self):
        directive = self.engine.process(
            "hello", {"complexity": 0.9}
        )
        assert directive.reasoning_level == "full"
        assert directive.must_plan


class TestSystemDirectiveDTO:

    def test_to_dict(self):
        d = SystemDirective(
            mode="chat", must_plan=False,
            must_use_tools=False, must_stream=False,
            reasoning_level="light", governance_level="balanced",
        )
        data = d.to_dict()
        assert data["mode"] == "chat"
        assert data["reasoning_level"] == "light"

    def test_frozen(self):
        d = SystemDirective(
            mode="chat", must_plan=False,
            must_use_tools=False, must_stream=False,
            reasoning_level="light", governance_level="balanced",
        )
        import pytest
        with pytest.raises(Exception):
            d.mode = "task"  # frozen, should raise

    def test_to_system_prompt(self):
        d = SystemDirective(
            mode="task", must_plan=True,
            must_use_tools=True, must_stream=True,
            reasoning_level="deep", governance_level="balanced",
        )
        prompt = d.to_system_prompt()
        assert "MODE: task" in prompt
        assert "MUST_PLAN: True" in prompt
        assert "MUST_USE_TOOLS: True" in prompt
        assert "DVEXA SYSTEM DIRECTIVE" in prompt

    def test_default_directive(self):
        from governance.system_directive_engine import _DEFAULT_DIRECTIVE
        assert _DEFAULT_DIRECTIVE.mode == RuntimeMode.CHAT
        assert not _DEFAULT_DIRECTIVE.must_plan


class TestDirectiveIntegration:

    def test_create_directive_convenience(self):
        from governance.system_directive_engine import create_directive
        d = create_directive("hello")
        assert isinstance(d, SystemDirective)
        assert d.mode == RuntimeMode.CHAT

    def test_create_directive_with_context(self):
        from governance.system_directive_engine import create_directive
        d = create_directive("fix bug", {"has_tools": True})
        assert d.mode == RuntimeMode.TOOL

    def test_runtime_mode_enum_values(self):
        assert RuntimeMode.CHAT == "chat"
        assert RuntimeMode.TASK == "task"
        assert RuntimeMode.TOOL == "tool"
        assert RuntimeMode.EXPLORE == "explore"
        assert RuntimeMode.SYSTEM == "system"
