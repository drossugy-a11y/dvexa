"""Tests for Governance Strategy Layer."""
import pytest
from governance.strategy_layer import (
    GovernanceStrategyLayer,
    _to_skill_name,
    _STRATEGY_CONFIGS,
)
from governance.decision_layer import DecisionInjectionLayer


# ─── Mock Governance Objects ─────────────────────────────────────────────

class MockSkillScore:
    def __init__(self, combined_score=0.8, usage=10, consecutive_failures=0):
        self.combined_score = combined_score
        self.usage = usage
        self.consecutive_failures = consecutive_failures


class MockStatus:
    def __init__(self, value):
        self.value = value


class MockGovernor:
    """Mock SkillGovernor 返回可控的 lifecycle/policy/score。"""

    def __init__(self):
        self._statuses = {}
        self._scores = {}
        self._policies = {}

    def set_status(self, skill: str, status: str):
        self._statuses[skill] = MockStatus(status)

    def set_score(self, skill: str, score: float, usage=10, failures=0):
        self._scores[skill] = MockSkillScore(score, usage, failures)

    def set_policy(self, skill: str, allowed: bool):
        self._policies[skill] = allowed

    def get_status(self, skill: str):
        return self._statuses.get(skill, MockStatus("experimental"))

    def get_score(self, skill: str):
        return self._scores.get(skill)

    def check_skill_allowed(self, skill: str) -> bool:
        return self._policies.get(skill, True)


class MockRiskLevel:
    def __init__(self, value):
        self.value = value


class MockATSReport:
    def __init__(self, passed=True, risk_level="low", risk_score=0.0, summary="mock"):
        self.passed = passed
        self.risk_level = MockRiskLevel(risk_level)
        self.risk_score = risk_score
        self.summary = summary
        self.phases = []
        self.target = "mock"


class MockATS:
    def __init__(self):
        self._reports = {}
        self._default = MockATSReport()

    def set_default(self, report: MockATSReport):
        self._default = report

    def set_report(self, action: str, report: MockATSReport):
        self._reports[action] = report

    def run(self, target: str, context: dict):
        return self._reports.get(target, self._default)


# ─── Fixtures ──────────────────────────────────────────────────────────

def make_plan(steps: list[dict]) -> dict:
    return {"goal": "test", "steps": steps}


SAMPLE_STEPS = [
    {"id": 1, "action": "analyze data", "type": "tool", "tool": "llm"},
    {"id": 2, "action": "execute code", "type": "tool", "tool": "code_executor"},
    {"id": 3, "action": "summarize results", "type": "tool", "tool": "llm"},
]

EMPTY_TASK: dict = {}


# ═══════════════════════════════════════════════════════════════════════
# 策略选择
# ═══════════════════════════════════════════════════════════════════════

class TestSelectStrategy:

    # ── STRICT ──────────────────────────────────────────────────────────

    def test_strict_high_risk_ats(self):
        """ATS HIGH risk → STRICT。"""
        ats = MockATS()
        ats.set_default(MockATSReport(passed=True, risk_level="high", risk_score=0.7))
        layer = GovernanceStrategyLayer(ats=ats)

        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "STRICT"

    def test_strict_ats_fail(self):
        """ATS fail → STRICT。"""
        ats = MockATS()
        ats.set_default(MockATSReport(passed=False, risk_level="low", summary="failed"))
        layer = GovernanceStrategyLayer(ats=ats)

        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "STRICT"

    def test_strict_quarantined(self):
        """Lifecycle QUARANTINED → STRICT。"""
        governor = MockGovernor()
        governor.set_status("code", "quarantined")
        layer = GovernanceStrategyLayer(skill_governor=governor)

        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "STRICT"

    def test_strict_multiple_deny(self):
        """多个工具被 deny → STRICT。"""
        governor = MockGovernor()
        governor.set_policy("code", False)
        governor.set_policy("http", False)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "STRICT"

    # ── CONSERVATIVE ────────────────────────────────────────────────────

    def test_conservative_financial_keyword(self):
        """金融关键词 → CONSERVATIVE。"""
        layer = GovernanceStrategyLayer()
        task = {"task": "执行交易计算", "input": "计算收益率"}

        strategy = layer.select_strategy(task, make_plan(SAMPLE_STEPS))
        assert strategy == "CONSERVATIVE"

    def test_conservative_security_keyword(self):
        """安全关键词 → CONSERVATIVE。"""
        layer = GovernanceStrategyLayer()
        task = {"task": "security scan the codebase"}

        strategy = layer.select_strategy(task, make_plan(SAMPLE_STEPS))
        assert strategy == "CONSERVATIVE"

    def test_conservative_network_keyword(self):
        """网络请求关键词 → CONSERVATIVE。"""
        layer = GovernanceStrategyLayer()
        task = {"task": "发送 HTTP 请求获取数据"}

        strategy = layer.select_strategy(task, make_plan(SAMPLE_STEPS))
        assert strategy == "CONSERVATIVE"

    def test_conservative_repeated_failures(self):
        """重复失败 → CONSERVATIVE。"""
        governor = MockGovernor()
        governor.set_score("code", 0.4, usage=20, failures=5)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "CONSERVATIVE"

    # ── EXPLORATION ─────────────────────────────────────────────────────

    def test_exploration_low_score(self):
        """低评分技能 → EXPLORATION。"""
        governor = MockGovernor()
        governor.set_score("code", 0.15, usage=10)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "EXPLORATION"

    def test_exploration_unknown_tool(self):
        """未知工具 → EXPLORATION。"""
        governor = MockGovernor()
        layer = GovernanceStrategyLayer(skill_governor=governor)
        plan = make_plan([
            {"id": 1, "action": "do something", "type": "tool", "tool": "unknown_tool"},
        ])

        strategy = layer.select_strategy(EMPTY_TASK, plan)
        assert strategy == "EXPLORATION"

    def test_exploration_first_time_skill(self):
        """首次使用的技能 → EXPLORATION。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=0)  # usage = 0
        layer = GovernanceStrategyLayer(skill_governor=governor)

        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "EXPLORATION"

    # ── BALANCED ────────────────────────────────────────────────────────

    def test_balanced_default(self):
        """正常条件 → BALANCED。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=50)
        governor.set_score("code", 0.9, usage=30)
        ats = MockATS()
        ats.set_default(MockATSReport(passed=True, risk_level="low"))
        layer = GovernanceStrategyLayer(skill_governor=governor, ats=ats)

        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "BALANCED"

    def test_balanced_no_governance(self):
        """无 governor/ATS → BALANCED。"""
        layer = GovernanceStrategyLayer()
        strategy = layer.select_strategy(EMPTY_TASK, make_plan(SAMPLE_STEPS))
        assert strategy == "BALANCED"


# ═══════════════════════════════════════════════════════════════════════
# 策略应用
# ═══════════════════════════════════════════════════════════════════════

class TestApplyStrategy:

    def test_apply_strategy_balanced_normal(self):
        """BALANCED: 正常过滤，步骤保留。"""
        layer = GovernanceStrategyLayer()
        plan = make_plan(SAMPLE_STEPS)

        result = layer.apply_strategy("BALANCED", plan)
        assert result["strategy_used"] == "BALANCED"
        assert len(result["filtered_plan"]["steps"]) == 3
        assert len(result["decisions"]) >= 3

    def test_apply_strategy_balanced_with_governor(self):
        """BALANCED + governor: steps 带 score 检查。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.85, usage=50)
        governor.set_score("code", 0.9, usage=30)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        plan = make_plan(SAMPLE_STEPS)
        result = layer.apply_strategy("BALANCED", plan)
        assert len(result["filtered_plan"]["steps"]) == 3

    def test_apply_strategy_strict_blocks_high_risk(self):
        """STRICT + ATS HIGH risk → block。"""
        ats = MockATS()
        ats.set_default(MockATSReport(passed=False, risk_level="high", summary="risky"))
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=10)
        governor.set_score("code", 0.8, usage=10)
        layer = GovernanceStrategyLayer(skill_governor=governor, ats=ats)

        plan = make_plan([
            {"id": 1, "action": "risky_op", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.apply_strategy("STRICT", plan)
        # ATS check runs before lifecycle → blocks in ATS checkpoint
        assert len(result["filtered_plan"]["steps"]) == 0
        assert any(d["action"] == "block" for d in result["decisions"])

    def test_apply_strategy_strict_downgrades_experimental(self):
        """STRICT: experimental skill → downgrade。"""
        governor = MockGovernor()
        governor.set_score("code", 0.8, usage=5)  # usage < 10 → experimental
        layer = GovernanceStrategyLayer(skill_governor=governor)

        plan = make_plan([
            {"id": 1, "action": "run", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.apply_strategy("STRICT", plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["type"] == "reasoning"

    def test_apply_strategy_exploration_prefers_reasoning(self):
        """EXPLORATION: prefer_reasoning → all become reasoning。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=10)
        governor.set_score("code", 0.8, usage=10)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        plan = make_plan([
            {"id": 1, "action": "compute", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.apply_strategy("EXPLORATION", plan)
        step = result["filtered_plan"]["steps"][0]
        # EXPLORATION with prefer_reasoning=True → tool steps become reasoning
        assert step["type"] == "reasoning"

    def test_apply_strategy_conservative_blocks_network(self):
        """CONSERVATIVE: 阻断网络工具。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=10)
        governor.set_score("http", 0.8, usage=10)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        plan = make_plan([
            {"id": 1, "action": "fetch", "type": "tool", "tool": "http_request"},
        ])
        result = layer.apply_strategy("CONSERVATIVE", plan)
        assert len(result["filtered_plan"]["steps"]) == 0
        assert any(d["action"] == "block" for d in result["decisions"])

    def test_apply_strategy_conservative_prefers_reasoning(self):
        """CONSERVATIVE: 非网络工具也转为 reasoning。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=10)
        governor.set_score("code", 0.8, usage=10)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        plan = make_plan([
            {"id": 1, "action": "compute", "type": "tool", "tool": "code_executor"},
        ])
        result = layer.apply_strategy("CONSERVATIVE", plan)
        step = result["filtered_plan"]["steps"][0]
        assert step["type"] == "reasoning"

    def test_apply_strategy_output_format(self):
        """输出格式包含 strategy_used。"""
        layer = GovernanceStrategyLayer()

        result = layer.apply_strategy("BALANCED", make_plan(SAMPLE_STEPS))
        assert "filtered_plan" in result
        assert "decisions" in result
        assert "strategy_used" in result
        assert result["strategy_used"] == "BALANCED"

    def test_apply_strategy_empty_plan(self):
        """空 plan 不崩溃。"""
        layer = GovernanceStrategyLayer()

        result = layer.apply_strategy("STRICT", {"goal": "x"})
        assert result["filtered_plan"] == {"goal": "x"}  # returned as-is
        assert result["decisions"] == []
        assert result["strategy_used"] == "STRICT"

    def test_apply_strategy_all_strategies_produce_output(self):
        """全部 4 种策略都能产生有效输出。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=10)
        governor.set_score("code", 0.8, usage=10)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        for strategy in ("STRICT", "BALANCED", "EXPLORATION", "CONSERVATIVE"):
            result = layer.apply_strategy(strategy, make_plan(SAMPLE_STEPS))
            assert "filtered_plan" in result
            assert "decisions" in result
            assert result["strategy_used"] == strategy
            # All strategies should produce at least some decisions
            assert len(result["decisions"]) > 0


# ═══════════════════════════════════════════════════════════════════════
# DecisionInjectionLayer 集成
# ═══════════════════════════════════════════════════════════════════════

class TestDecisionInjectionLayerWithStrategy:

    def test_inject_with_strategy_layer(self):
        """inject() 使用策略层进行过滤。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=50)
        governor.set_score("code", 0.9, usage=30)
        strategy_layer = GovernanceStrategyLayer(skill_governor=governor)
        layer = DecisionInjectionLayer(governor=governor, strategy_layer=strategy_layer)

        result = layer.inject(make_plan(SAMPLE_STEPS))
        assert "strategy_used" in result
        assert result["strategy_used"] == "BALANCED"
        assert len(result["filtered_plan"]["steps"]) == 3

    def test_inject_strategy_reroutes_unknown_tool(self):
        """通过策略层：未知工具被 reroute 到 llm。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=10)
        strategy_layer = GovernanceStrategyLayer(skill_governor=governor)
        layer = DecisionInjectionLayer(governor=governor, strategy_layer=strategy_layer)

        plan = make_plan([
            {"id": 1, "action": "do something", "type": "tool", "tool": "unknown_tool"},
        ])
        result = layer.inject(plan)
        steps = result["filtered_plan"]["steps"]
        assert len(steps) == 1
        # EXPLORATION prefer_reasoning → step downgraded to reasoning, tool removed
        assert steps[0]["type"] == "reasoning"
        assert "tool" not in steps[0]
        assert result["strategy_used"] == "EXPLORATION"

    def test_inject_strategy_blocks_network_conservative(self):
        """保守策略阻断网络工具。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=10)
        governor.set_score("http", 0.8, usage=10)
        strategy_layer = GovernanceStrategyLayer(skill_governor=governor)
        layer = DecisionInjectionLayer(governor=governor, strategy_layer=strategy_layer)

        plan = make_plan([
            {"id": 1, "action": "发送 HTTP 请求", "type": "tool", "tool": "http_request"},
        ])
        result = layer.inject(plan, task_context={"task": "网络请求"})
        assert result["strategy_used"] == "CONSERVATIVE"
        assert len(result["filtered_plan"]["steps"]) == 0

    def test_inject_task_context_affects_strategy(self):
        """task_context 影响策略选择。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=50)
        governor.set_score("code", 0.9, usage=30)
        strategy_layer = GovernanceStrategyLayer(skill_governor=governor)
        layer = DecisionInjectionLayer(governor=governor, strategy_layer=strategy_layer)

        # Without task context → BALANCED
        result1 = layer.inject(make_plan(SAMPLE_STEPS))
        assert result1["strategy_used"] == "BALANCED"

        # With security task context → CONSERVATIVE
        result2 = layer.inject(make_plan(SAMPLE_STEPS),
                               task_context={"task": "security audit"})
        assert result2["strategy_used"] == "CONSERVATIVE"

    def test_inject_no_strategy_layer_backward_compat(self):
        """GovernanceKernel inject() 兼容 DecisionInjectionLayer 接口。"""
        layer = DecisionInjectionLayer()
        result = layer.inject(make_plan(SAMPLE_STEPS))
        # kernel 总是包含 strategy_used（与旧版不同，但功能兼容）
        assert result.get("strategy_used") is not None
        assert len(result["filtered_plan"]["steps"]) == 3
        assert len(result["decisions"]) >= 3

    def test_inject_strategy_layer_decisions_trace(self):
        """strategy_layer 的 decisions 每步都有 reason。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=50)
        strategy_layer = GovernanceStrategyLayer(skill_governor=governor)
        layer = DecisionInjectionLayer(governor=governor, strategy_layer=strategy_layer)

        result = layer.inject(make_plan(SAMPLE_STEPS))
        for d in result["decisions"]:
            assert "step_id" in d
            assert "action" in d
            assert "reason" in d

    def test_inject_empty_plan_with_strategy(self):
        """空 plan + strategy_layer 不崩溃。"""
        strategy_layer = GovernanceStrategyLayer()
        layer = DecisionInjectionLayer(strategy_layer=strategy_layer)

        assert layer.inject(None)["filtered_plan"] is None
        result = layer.inject({})
        assert result["filtered_plan"] == {}
        assert result.get("strategy_used") is not None


# ═══════════════════════════════════════════════════════════════════════
# 确定性验证
# ═══════════════════════════════════════════════════════════════════════

class TestDeterminism:

    def test_same_input_same_strategy(self):
        """相同输入总是产生相同策略。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=50)
        layer = GovernanceStrategyLayer(skill_governor=governor)
        plan = make_plan(SAMPLE_STEPS)

        results = [layer.select_strategy(EMPTY_TASK, plan) for _ in range(5)]
        assert all(r == results[0] for r in results)

    def test_same_input_same_decisions(self):
        """相同输入总是产生相同 decisions。"""
        governor = MockGovernor()
        governor.set_score("llm", 0.8, usage=50)
        governor.set_score("code", 0.9, usage=30)
        layer = GovernanceStrategyLayer(skill_governor=governor)

        plan = make_plan(SAMPLE_STEPS)
        r1 = layer.apply_strategy("BALANCED", plan)
        r2 = layer.apply_strategy("BALANCED", plan)

        assert r1["decisions"] == r2["decisions"]
        assert r1["filtered_plan"] == r2["filtered_plan"]


# ═══════════════════════════════════════════════════════════════════════
# 策略配置
# ═══════════════════════════════════════════════════════════════════════

class TestStrategyConfig:

    def test_all_strategies_have_config(self):
        """全部 4 种策略都有配置。"""
        for name in ("STRICT", "BALANCED", "EXPLORATION", "CONSERVATIVE"):
            config = _STRATEGY_CONFIGS.get(name)
            assert config is not None, f"Missing config for {name}"
            assert "label" in config
            assert "skill_score_threshold" in config
            assert "ats_risk_threshold" in config

    def test_config_thresholds_differ(self):
        """各策略有不同的阈值。"""
        strict_ss = _STRATEGY_CONFIGS["STRICT"]["skill_score_threshold"]
        exploration_ss = _STRATEGY_CONFIGS["EXPLORATION"]["skill_score_threshold"]
        assert strict_ss > exploration_ss  # STRICT stricter

    @pytest.mark.parametrize("strategy,expected_network_block", [
        ("STRICT", False),
        ("BALANCED", False),
        ("EXPLORATION", False),
        ("CONSERVATIVE", True),
    ])
    def test_network_block_only_conservative(self, strategy, expected_network_block):
        """只有 CONSERVATIVE 阻断网络工具。"""
        config = _STRATEGY_CONFIGS[strategy]
        assert config["block_network_tools"] == expected_network_block


# ═══════════════════════════════════════════════════════════════════════
# _to_skill_name 复用
# ═══════════════════════════════════════════════════════════════════════

class TestToolNameMapping:
    def test_mapping_consistent(self):
        """策略层的映射与 decision_layer 一致。"""
        from governance.decision_layer import _to_skill_name as dl_to_skill
        for tool in ("code_executor", "http_request", "llm", "github", "security", "unknown"):
            assert _to_skill_name(tool) == dl_to_skill(tool)
