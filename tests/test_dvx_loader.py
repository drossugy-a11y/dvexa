"""Tests for DVX Language v0.1 — DVXLoader"""

import pytest
from governance.dvx_loader import DVXLoader, DVXAction, DVXParseError


class TestDVXLoaderBasicParsing:
    """测试基本 ACTION 解析"""

    def setup_method(self):
        self.loader = DVXLoader()

    def test_parse_basic_action(self):
        """基本 ACTION 解析"""
        result = self.loader.parse(
            'ACTION config_loader { intent: "analysis", mode: "observe" }'
        )
        assert isinstance(result, DVXAction)
        assert result.target == "config_loader"
        assert result.intent == "analysis"
        assert result.mode == "observe"

    def test_parse_with_all_fields(self):
        """所有字段都指定"""
        result = self.loader.parse(
            'ACTION scanner {\n'
            '    intent: "execution",\n'
            '    mode: "strict",\n'
            '    constraint: "read-only",\n'
            '    output: "scan report"\n'
            '}'
        )
        assert result.target == "scanner"
        assert result.intent == "execution"
        assert result.mode == "strict"
        assert result.constraint == "read-only"
        assert result.output == "scan report"

    def test_parse_default_values(self):
        """缺省字段使用默认值"""
        result = self.loader.parse('ACTION test { }')
        assert result.target == "test"
        assert result.intent == "analysis"
        assert result.mode == "observe"
        assert result.constraint is None
        assert result.output is None

    def test_parse_with_extra_whitespace(self):
        """多余空白不影响解析"""
        result = self.loader.parse('   ACTION   my_module   {   intent:   "execution"   }   ')
        assert result.target == "my_module"
        assert result.intent == "execution"

    def test_parse_empty_input_raises(self):
        """空输入抛出 DVXParseError"""
        with pytest.raises(DVXParseError, match="Empty input"):
            self.loader.parse("")

    def test_parse_whitespace_only_raises(self):
        """纯空白输入抛出 DVXParseError"""
        with pytest.raises(DVXParseError, match="Empty input"):
            self.loader.parse("   \n  \t  ")

    def test_parse_no_action_format_raises(self):
        """非 ACTION 格式抛出 DVXParseError"""
        with pytest.raises(DVXParseError, match="No valid ACTION block"):
            self.loader.parse("just some random text")

    def test_parse_partial_action_format_raises(self):
        """不完整的 ACTION 格式抛出 DVXParseError"""
        with pytest.raises(DVXParseError, match="No valid ACTION block"):
            self.loader.parse("ACTION something")


class TestDVXLoaderIntents:
    """测试所有 intent 值"""

    def setup_method(self):
        self.loader = DVXLoader()

    def test_intent_analysis(self):
        result = self.loader.parse('ACTION x { intent: "analysis" }')
        assert result.intent == "analysis"

    def test_intent_execution(self):
        result = self.loader.parse('ACTION x { intent: "execution" }')
        assert result.intent == "execution"

    def test_intent_manipulation(self):
        result = self.loader.parse('ACTION x { intent: "manipulation" }')
        assert result.intent == "manipulation"

    def test_intent_extraction(self):
        result = self.loader.parse('ACTION x { intent: "extraction" }')
        assert result.intent == "extraction"

    def test_intent_unknown(self):
        result = self.loader.parse('ACTION x { intent: "unknown" }')
        assert result.intent == "unknown"

    def test_invalid_intent_fallback(self):
        """无效 intent 回退到 'unknown' 并添加警告"""
        result = self.loader.parse('ACTION x { intent: "invalid_intent" }')
        assert result.intent == "unknown"
        assert len(result.warnings) >= 1
        assert "invalid_intent" in result.warnings[0]


class TestDVXLoaderModes:
    """测试所有 mode 值"""

    def setup_method(self):
        self.loader = DVXLoader()

    def test_mode_observe(self):
        result = self.loader.parse('ACTION x { mode: "observe" }')
        assert result.mode == "observe"

    def test_mode_strict(self):
        result = self.loader.parse('ACTION x { mode: "strict" }')
        assert result.mode == "strict"

    def test_mode_simulate(self):
        result = self.loader.parse('ACTION x { mode: "simulate" }')
        assert result.mode == "simulate"

    def test_invalid_mode_fallback(self):
        """无效 mode 回退到 'observe' 并添加警告"""
        result = self.loader.parse('ACTION x { mode: "danger" }')
        assert result.mode == "observe"
        assert len(result.warnings) >= 1
        assert "danger" in result.warnings[0]

    def test_mode_default_when_not_specified(self):
        """未指定 mode 时默认为 observe"""
        result = self.loader.parse('ACTION x { intent: "analysis" }')
        assert result.mode == "observe"


class TestDVXLoaderMultiAction:
    """测试多 ACTION 解析"""

    def setup_method(self):
        self.loader = DVXLoader()

    def test_parse_multi_two_actions(self):
        """解析包含两个 ACTION 块的文本"""
        text = (
            'ACTION scanner { intent: "analysis" }\n'
            'ACTION executor { intent: "execution", mode: "strict" }'
        )
        results = self.loader.parse_multi(text)
        assert len(results) == 2
        assert results[0].target == "scanner"
        assert results[0].intent == "analysis"
        assert results[1].target == "executor"
        assert results[1].intent == "execution"
        assert results[1].mode == "strict"

    def test_parse_multi_empty_text(self):
        """空文本返回空列表"""
        assert self.loader.parse_multi("") == []
        assert self.loader.parse_multi("   ") == []

    def test_parse_multi_skips_invalid(self):
        """无效 ACTION 块被跳过"""
        text = (
            'ACTION valid { intent: "analysis" }\n'
            'not an action\n'
            'ACTION { }'  # missing target
        )
        results = self.loader.parse_multi(text)
        assert len(results) == 1
        assert results[0].target == "valid"

    def test_parse_multi_with_mixed_content(self):
        """混合文本中提取 ACTION 块"""
        text = (
            "Some preamble text...\n"
            'ACTION module_a { intent: "extraction", mode: "observe" }\n'
            "More text in between\n"
            'ACTION module_b { intent: "execution", mode: "strict", '
            'constraint: "timeout 30s" }\n'
            "Trailing text."
        )
        results = self.loader.parse_multi(text)
        assert len(results) == 2
        assert results[0].target == "module_a"
        assert results[0].intent == "extraction"
        assert results[1].target == "module_b"
        assert results[1].constraint == "timeout 30s"


class TestDVXLoaderIsAction:
    """测试 is_action 检查"""

    def setup_method(self):
        self.loader = DVXLoader()

    def test_is_action_true(self):
        assert self.loader.is_action('ACTION x { }') is True
        assert self.loader.is_action('ACTION target { intent: "analysis" }') is True

    def test_is_action_false_for_plain_text(self):
        assert self.loader.is_action("hello world") is False

    def test_is_action_false_for_empty(self):
        assert self.loader.is_action("") is False
        assert self.loader.is_action("  ") is False

    def test_is_action_false_for_partial(self):
        assert self.loader.is_action("ACTION x") is False  # no braces


class TestDVXLoaderValidate:
    """测试 validate 方法"""

    def setup_method(self):
        self.loader = DVXLoader()

    def test_validate_valid_action(self):
        """有效 action 不产生警告"""
        action = DVXAction(target="test", intent="analysis", mode="observe")
        result = self.loader.validate(action)
        assert result.warnings == []

    def test_validate_invalid_intent_adds_warning(self):
        action = DVXAction(target="test", intent="bad_intent", mode="observe")
        result = self.loader.validate(action)
        assert "bad_intent" in result.warnings[0]
        assert result.intent == "unknown"

    def test_validate_invalid_mode_adds_warning(self):
        action = DVXAction(target="test", intent="analysis", mode="danger_mode")
        result = self.loader.validate(action)
        assert "danger_mode" in result.warnings[0]
        assert result.mode == "observe"

    def test_validate_invalid_intent_and_mode(self):
        action = DVXAction(target="test", intent="bad", mode="wrong")
        result = self.loader.validate(action)
        assert len(result.warnings) == 2
        assert result.intent == "unknown"
        assert result.mode == "observe"


class TestDVXLoaderEdgeCases:
    """测试边界情况"""

    def setup_method(self):
        self.loader = DVXLoader()

    def test_multiline_body(self):
        """多行 body 内容"""
        text = (
            'ACTION analyzer {\n'
            '    intent: "analysis",\n'
            '    mode: "observe",\n'
            '    constraint: "max 10MB input",\n'
            '    output: "summary report"\n'
            '}'
        )
        result = self.loader.parse(text)
        assert result.target == "analyzer"
        assert result.constraint == "max 10MB input"
        assert result.output == "summary report"

    def test_fields_in_different_order(self):
        """字段顺序不影响解析"""
        result = self.loader.parse(
            'ACTION test { mode: "strict", intent: "execution", output: "log" }'
        )
        assert result.intent == "execution"
        assert result.mode == "strict"
        assert result.output == "log"

    def test_unknown_fields_ignored(self):
        """未知字段被忽略（不报错）"""
        result = self.loader.parse(
            'ACTION test { intent: "analysis", extra: "ignored", unknown: "field" }'
        )
        assert result.intent == "analysis"

    def test_single_quotes_not_supported(self):
        """单引号不被识别为字段值"""
        result = self.loader.parse(
            "ACTION test { intent: 'analysis', mode: 'observe' }"
        )
        # 字段未匹配到双引号值，使用默认值
        assert result.intent == "analysis"  # 默认值
        assert result.mode == "observe"  # 默认值

    def test_target_with_dots(self):
        """目标名包含点号"""
        result = self.loader.parse('ACTION external.github { intent: "extraction" }')
        assert result.target == "external.github"

    def test_target_with_hyphens(self):
        """目标名包含连字符"""
        result = self.loader.parse('ACTION my-module { intent: "analysis" }')
        assert result.target == "my-module"

    def test_raw_text_preserved(self):
        """原始输入文本被保存"""
        text = 'ACTION test { intent: "analysis" }'
        result = self.loader.parse(text)
        assert result.raw == text

    def test_parse_multi_all_invalid(self):
        """全无效的多 ACTION 返回空列表"""
        text = "not action\nstill not\nnope"
        results = self.loader.parse_multi(text)
        assert results == []
