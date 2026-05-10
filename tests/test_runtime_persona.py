"""Tests for Runtime Persona Kernel v2 — 系统级身份注入"""

from __future__ import annotations

from runtime.persona.runtime_persona import RuntimePersonaKernel
from runtime.persona.persona_types import PersonaProfile, RuntimePersona
from runtime.persona.directive_profiles import resolve_profile, PROFILES


class _FakeDirective:
    def __init__(self, mode: str = "chat"):
        self.mode = mode
        self.must_plan = False
        self.must_stream = False


class _FakeTurn:
    def __init__(self, directive=None):
        self.directive = directive
        self.mode = getattr(directive, 'mode', 'chat') if directive else 'chat'


class TestRuntimePersonaKernel:

    def setup_method(self):
        self.kernel = RuntimePersonaKernel()

    def test_default_profile_is_lightweight(self):
        assert self.kernel.active_profile == PersonaProfile.LIGHTWEIGHT

    def test_default_prompt_is_non_empty(self):
        prompt = self.kernel.get_system_prompt()
        assert len(prompt) > 50
        assert "DVexa Runtime" in prompt

    def test_set_for_task_chat(self):
        self.kernel.set_for_task(_FakeDirective("chat"))
        assert self.kernel.active_profile == PersonaProfile.LIGHTWEIGHT

    def test_set_for_task_standard(self):
        self.kernel.set_for_task(_FakeDirective("task"))
        assert self.kernel.active_profile in (
            PersonaProfile.STANDARD, PersonaProfile.CODING,
        )

    def test_set_for_task_governance(self):
        self.kernel.set_for_task(_FakeDirective("system"))
        assert self.kernel.active_profile == PersonaProfile.GOVERNANCE

    def test_persona_changes_with_mode(self):
        self.kernel.set_for_task(_FakeDirective("chat"))
        chat_prompt = self.kernel.get_system_prompt()
        self.kernel.set_for_task(_FakeDirective("task"))
        task_prompt = self.kernel.get_system_prompt()
        assert chat_prompt != task_prompt

    def test_reset_returns_to_lightweight(self):
        self.kernel.set_for_task(_FakeDirective("task"))
        self.kernel.reset()
        assert self.kernel.active_profile == PersonaProfile.LIGHTWEIGHT

    def test_is_lightweight_initially(self):
        assert self.kernel.is_lightweight() is True

    def test_is_lightweight_after_task(self):
        self.kernel.set_for_task(_FakeDirective("task"))
        assert self.kernel.is_lightweight() is False

    def test_is_lightweight_after_reset(self):
        self.kernel.set_for_task(_FakeDirective("task"))
        self.kernel.reset()
        assert self.kernel.is_lightweight() is True

    def test_no_chatbot_identity_in_prompt(self):
        prompt = self.kernel.get_system_prompt()
        assert "generic chatbot" in prompt
        assert "DVexa Runtime" in prompt


class TestResolveProfile:

    def test_chat_returns_lightweight(self):
        assert resolve_profile("chat", 0.0) == PersonaProfile.LIGHTWEIGHT

    def test_chat_high_complexity_returns_standard(self):
        assert resolve_profile("chat", 0.5) == PersonaProfile.STANDARD

    def test_task_returns_standard(self):
        assert resolve_profile("task", 0.3) == PersonaProfile.STANDARD

    def test_task_high_complexity_returns_coding(self):
        assert resolve_profile("task", 0.6) == PersonaProfile.CODING

    def test_system_returns_governance(self):
        assert resolve_profile("system", 0.0) == PersonaProfile.GOVERNANCE

    def test_tool_returns_standard(self):
        assert resolve_profile("tool", 0.3) == PersonaProfile.STANDARD

    def test_explore_returns_standard(self):
        assert resolve_profile("explore", 0.0) == PersonaProfile.STANDARD


class TestLLMToolPersona:

    def test_llm_tool_accepts_persona(self):
        """验证 LLMTool 的 runtime_persona 接口。"""
        from tools.llm_tool import LLMTool
        from unittest.mock import MagicMock
        tool = LLMTool(api_key="test", base_url="http://test", model="test")
        tool.client = MagicMock()
        tool.set_runtime_persona("TEST PERSONA")
        assert tool._runtime_persona == "TEST PERSONA"

    def test_llm_tool_persona_in_system_message(self):
        """验证 persona 出现在 system message 中且优先级最高。"""
        from tools.llm_tool import LLMTool
        from unittest.mock import MagicMock
        tool = LLMTool(api_key="test", base_url="http://test", model="test")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        tool.client.chat.completions.create = MagicMock(return_value=mock_response)

        tool.set_runtime_persona("RUNTIME IDENTITY")
        tool.call("hello", system_prompt="TASK PROMPT")

        sent_messages = tool.client.chat.completions.create.call_args[1]["messages"]
        system_msgs = [m for m in sent_messages if m["role"] == "system"]
        assert len(system_msgs) == 1
        combined = system_msgs[0]["content"]
        assert combined.startswith("RUNTIME IDENTITY")
        assert "TASK PROMPT" in combined

    def test_llm_tool_persona_without_extra_system(self):
        """无额外 system_prompt 时 persona 单独使用。"""
        from tools.llm_tool import LLMTool
        from unittest.mock import MagicMock
        tool = LLMTool(api_key="test", base_url="http://test", model="test")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        tool.client.chat.completions.create = MagicMock(return_value=mock_response)

        tool.set_runtime_persona("RUNTIME IDENTITY")
        tool.call("hello")

        sent_messages = tool.client.chat.completions.create.call_args[1]["messages"]
        system_msgs = [m for m in sent_messages if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "RUNTIME IDENTITY"


class TestPersonaProfiles:

    def test_all_profiles_have_identity(self):
        for name, profile in PROFILES.items():
            assert len(profile.identity) > 20, f"{name} missing identity"
            assert "DVexa Runtime" in profile.identity, f"{name} wrong identity"

    def test_all_profiles_have_directives(self):
        for name, profile in PROFILES.items():
            assert len(profile.directives) > 0, f"{name} missing directives"

    def test_lightweight_has_no_chatbot_filler(self):
        profile = PROFILES[PersonaProfile.LIGHTWEIGHT]
        prompt = profile.to_system_prompt()
        assert "很高兴" not in prompt
        assert "您好" not in prompt
