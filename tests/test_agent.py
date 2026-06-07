"""Tests for base agent strategy detection."""

from agents.base_agent import BaseAgent, STRATEGY_TEMPLATES, safe_parse_plan


class MockLLM:
    def call(self, prompt, system_prompt=""):
        return {"content": '{"goal": "test", "steps": [{"id": 1, "action": "test", "tool": "analyst"}]}'}


class TestBaseAgent:
    def setup_method(self):
        self.agent = BaseAgent(MockLLM())

    def test_detect_value_strategy(self):
        assert BaseAgent._detect_strategy("找低PE高股息的股票") == "value"
        assert BaseAgent._detect_strategy("search for undervalued stocks") == "value"

    def test_detect_growth_strategy(self):
        assert BaseAgent._detect_strategy("找高成长的科技股") == "growth"
        assert BaseAgent._detect_strategy("growth stocks") == "growth"

    def test_detect_quality_strategy(self):
        assert BaseAgent._detect_strategy("找稳健的白马股") == "quality"
        assert BaseAgent._detect_strategy("quality stocks") == "quality"

    def test_detect_comprehensive_strategy(self):
        assert BaseAgent._detect_strategy("帮我选几只好股票") == "comprehensive"

    def test_plan_returns_valid_structure(self):
        result = self.agent.plan("帮我找低估值的消费股")
        assert "goal" in result
        assert "steps" in result
        assert isinstance(result["steps"], list)

    def test_strategy_templates_complete(self):
        for key in ["value", "growth", "quality", "comprehensive"]:
            assert key in STRATEGY_TEMPLATES
            template = STRATEGY_TEMPLATES[key]
            assert "name" in template
            assert "focus" in template
            assert "prompt" in template

    def test_safe_parse_plan_valid(self):
        data = safe_parse_plan('{"goal": "test", "steps": []}')
        assert data is not None
        assert data["goal"] == "test"

    def test_safe_parse_plan_invalid(self):
        assert safe_parse_plan("not json") is None
        assert safe_parse_plan("{}") is None
