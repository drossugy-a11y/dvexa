"""Tests for Tool Policy (Allow/Deny + Priority Chain)"""
import pytest

from governance.tool_policy import (
    ToolPolicy,
    is_tool_allowed,
    resolve_policy,
    default_policy,
    restricted_policy,
    expand_tool_list,
    TOOL_GROUPS,
)


# ─── 核心函数测试 ───────────────────────────────────────────────────

class TestIsToolAllowed:
    def test_default_policy_allows_all(self):
        policy = default_policy()
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "code") is True
        assert is_tool_allowed(policy, "unknown") is True  # 空 allow = 全部允许

    def test_deny_overrides_allow(self):
        policy = ToolPolicy(allow=["llm", "code"], deny=["code"])
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "code") is False

    def test_empty_allow_means_all(self):
        policy = ToolPolicy(allow=[], deny=[])
        assert is_tool_allowed(policy, "anything") is True

    def test_empty_allow_with_deny(self):
        policy = ToolPolicy(allow=[], deny=["evil"])
        assert is_tool_allowed(policy, "good") is True
        assert is_tool_allowed(policy, "evil") is False

    def test_explicit_allow_list(self):
        policy = ToolPolicy(allow=["llm"], deny=[])
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "code") is False

    def test_glob_pattern_deny(self):
        policy = ToolPolicy(allow=["all"], deny=["feishu_*"])
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "feishu_send") is False

    def test_group_allow(self):
        policy = ToolPolicy(allow=["readonly"], deny=[])
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "http") is True
        assert is_tool_allowed(policy, "code") is False
        assert is_tool_allowed(policy, "github") is True

    def test_group_deny(self):
        policy = ToolPolicy(allow=["all"], deny=["network"])
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "code") is True
        assert is_tool_allowed(policy, "http") is False
        assert is_tool_allowed(policy, "github") is False

    def test_case_insensitive(self):
        policy = ToolPolicy(allow=["LLM"], deny=[])
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "LLM") is True

    def test_unknown_tool_with_restricted_policy(self):
        policy = restricted_policy(["llm", "code"])
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "unknown") is False

    def test_deny_glob_prefix(self):
        policy = ToolPolicy(allow=["all"], deny=["telegram_*"])
        assert is_tool_allowed(policy, "telegram_send") is False
        assert is_tool_allowed(policy, "telegram_receive") is False
        assert is_tool_allowed(policy, "llm") is True


class TestExpand:
    def test_expand_group(self):
        assert expand_tool_list(["all"]) == ["llm", "code", "http", "github", "security"]

    def test_expand_unknown_keeps_as_is(self):
        assert expand_tool_list(["unknown_tool"]) == ["unknown_tool"]

    def test_expand_mixed(self):
        result = expand_tool_list(["llm", "readonly"])
        assert "llm" in result
        assert "http" in result
        assert "github" in result
        assert "security" in result

    def test_expand_empty(self):
        assert expand_tool_list([]) == []

    def test_all_groups_exist(self):
        """所有 TOOL_GROUPS 中的工具都在 'all' 组中。"""
        all_tools = set(TOOL_GROUPS["all"])
        for group_name, tools in TOOL_GROUPS.items():
            if group_name == "all":
                continue
            for t in tools:
                assert t in all_tools, f"{t} from {group_name} not in 'all'"


class TestResolvePolicy:
    def test_default_when_no_overrides(self):
        policy = resolve_policy()
        assert policy.allow == []  # 空 = 允许所有
        assert policy.deny == []

    def test_global_overrides_defaults(self):
        global_p = ToolPolicy(allow=["readonly"], deny=["code"])
        policy = resolve_policy(global_policy=global_p)
        assert "llm" in expand_tool_list(policy.allow)
        assert "code" not in expand_tool_list(policy.allow)

    def test_skill_specific_overrides_global(self):
        global_p = ToolPolicy(allow=["readonly"])
        skill_p = ToolPolicy(allow=["all"])
        policy = resolve_policy(skill_specific=skill_p, global_policy=global_p)
        assert "code" in expand_tool_list(policy.allow)

    def test_skill_deny_overrides_global(self):
        """Skill 级策略完全覆盖全局（优先级链语义）。"""
        global_p = ToolPolicy(allow=["all"], deny=["http"])
        skill_p = ToolPolicy(allow=["all"], deny=["code"])
        policy = resolve_policy(skill_specific=skill_p, global_policy=global_p)
        assert "code" in expand_tool_list(policy.deny)
        assert "http" not in expand_tool_list(policy.deny)

    def test_global_does_not_override_skill_allow(self):
        global_p = ToolPolicy(allow=["readonly"])
        skill_p = ToolPolicy(allow=["all"])
        policy = resolve_policy(skill_specific=skill_p, global_policy=global_p)
        assert is_tool_allowed(policy, "code") is True

    def test_skill_empty_allow_falls_back_to_global(self):
        global_p = ToolPolicy(allow=["readonly"])
        skill_p = ToolPolicy(allow=[], deny=[])
        policy = resolve_policy(skill_specific=skill_p, global_policy=global_p)
        # skill allow 为空 → fallback 到 global
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "code") is False


class TestRestrictedPolicy:
    def test_restricted_allow_only(self):
        policy = restricted_policy(["llm", "http"])
        assert is_tool_allowed(policy, "llm") is True
        assert is_tool_allowed(policy, "code") is False

    def test_restricted_default_all(self):
        policy = restricted_policy()
        assert is_tool_allowed(policy, "anything") is True


# ─── SkillGovernor 集成测试 ──────────────────────────────────────────

class TestGovernorPolicyIntegration:
    def test_default_policy_allows_new_skill(self):
        from governance.skill_governor import SkillGovernor
        governor = SkillGovernor()
        governor.register("test_skill", object())
        assert governor.check_skill_allowed("test_skill") is True

    def test_restrict_skill(self):
        from governance.skill_governor import SkillGovernor
        governor = SkillGovernor()
        governor.register("safe_skill", object())
        governor.register("unsafe_skill", object())

        governor.set_policy("unsafe_skill", ToolPolicy(allow=[], deny=["unsafe_skill"]))
        assert governor.check_skill_allowed("safe_skill") is True
        assert governor.check_skill_allowed("unsafe_skill") is False

    def test_global_policy_affects_all(self):
        from governance.skill_governor import SkillGovernor
        governor = SkillGovernor()
        governor.register("skill_a", object())
        governor.register("skill_b", object())

        governor.set_global_policy(ToolPolicy(allow=["readonly"], deny=[]))
        assert governor.check_skill_allowed("llm") is True
        assert governor.check_skill_allowed("code") is False

    def test_skill_policy_overrides_global(self):
        from governance.skill_governor import SkillGovernor
        governor = SkillGovernor()
        governor.register("admin", object())

        governor.set_global_policy(ToolPolicy(allow=["readonly"], deny=[]))
        governor.set_policy("admin", ToolPolicy(allow=["all"], deny=[]))
        assert governor.check_skill_allowed("code") is False  # admin 不在 all 中
        assert governor.check_skill_allowed("llm") is True

    def test_get_policy_returns_resolved(self):
        from governance.skill_governor import SkillGovernor
        governor = SkillGovernor()
        governor.register("my_skill", object())

        governor.set_global_policy(ToolPolicy(allow=["readonly"], deny=["http"]))
        policy = governor.get_policy("my_skill")
        assert "http" in expand_tool_list(policy.deny)
