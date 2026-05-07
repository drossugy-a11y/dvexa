"""Capability Layer 测试 — v1.7 能力增长隔离架构

测试范围：
  - SkillRegistry：注册、匹配、发现
  - CapabilityRouter：路由、tool_registry 构建
  - 技能接口适配：stateless, no decision
"""

import pytest
from capabilities.skill import SkillDef, SkillRegistry
from capabilities.router import CapabilityRouter


class FakeSkill:
    def call(self, input_data):
        return {"content": f"processed: {input_data}"}


class TestSkillDef:
    def test_skill_def_holds_attributes(self):
        skill = FakeSkill()
        sd = SkillDef("test", skill, ["kw1", "kw2"], "描述")
        assert sd.name == "test"
        assert sd.handler == skill
        assert sd.keywords == ["kw1", "kw2"]
        assert sd.description == "描述"

    def test_skill_def_default_keywords_empty(self):
        sd = SkillDef("test", FakeSkill())
        assert sd.keywords == []


class TestSkillRegistry:
    @pytest.fixture
    def registry(self):
        r = SkillRegistry()
        r.register("code", FakeSkill(), ["代码", "执行"], "代码执行")
        r.register("llm", FakeSkill(), ["问答", "chat"], "问答能力")
        return r

    def test_register_and_get(self, registry):
        skill = registry.get("code")
        assert skill is not None
        assert skill.name == "code"

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get("nonexistent") is None

    def test_match_by_keyword(self, registry):
        assert registry.match("写代码") == "code"
        assert registry.match("执行任务") == "code"

    def test_match_by_different_keyword(self, registry):
        assert registry.match("问答一下") == "llm"
        assert registry.match("chat一下") == "llm"

    def test_no_match_returns_none(self, registry):
        assert registry.match("不相关的内容") is None

    def test_all_skills_returns_copy(self, registry):
        skills = registry.all_skills()
        assert len(skills) == 2
        assert "code" in skills
        assert "llm" in skills

    def test_count(self, registry):
        assert registry.count == 2


class TestCapabilityRouter:
    @pytest.fixture
    def router(self):
        r = CapabilityRouter()
        r.register_skill("code", FakeSkill(), ["代码", "执行"])
        r.register_skill("llm", FakeSkill(), ["问答", "chat"])
        return r

    def test_match_delegates_to_registry(self, router):
        assert router.match("写代码") == "code"
        assert router.match("问答") == "llm"

    def test_build_tool_registry_contains_skills(self, router):
        registry = router.build_tool_registry()
        assert "code" in registry
        assert "llm" in registry

    def test_build_tool_registry_includes_executor_aliases(self, router):
        registry = router.build_tool_registry()
        assert "code_executor" in registry
        assert "http_request" not in registry  # 未注册 http

    def test_router_skill_is_callable(self, router):
        registry = router.build_tool_registry()
        result = registry["llm"].call("hello")
        assert "processed: hello" in result.get("content", "")

    def test_router_call_requires_json_input(self, router):
        result = router.call("plain text")
        assert "需指定技能名" in result.get("content", "")

    def test_skill_count(self, router):
        assert router.skill_count == 2

    def test_register_skill_increments_count(self, router):
        router.register_skill("http", FakeSkill(), ["网络"])
        assert router.skill_count == 3
