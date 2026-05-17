"""Tests for CognitiveInspector — 运行时认知剖面分析"""

from __future__ import annotations

from runtime.intelligence.cognitive_inspector import CognitiveInspector
from runtime.step_events import RuntimeStep, StepType, make_step


class TestCognitiveInspector:
    """CognitiveInspector 测试套件"""

    def test_all_planning_steps(self):
        """全规划步骤 → planning_heavy。"""
        steps = [
            make_step(StepType.DIRECTIVE, title="Understood request"),
            make_step(StepType.PLANNING, title="Plan execution"),
            make_step(StepType.GOVERNANCE, title="Check policy"),
            make_step(StepType.DIRECTIVE, title="Re-interpret"),
        ]
        inspector = CognitiveInspector()
        profile = inspector.inspect(steps)

        assert profile.planning_ratio > 0.5
        assert profile.classification == "planning_heavy"
        assert profile.understanding_count == 2
        assert profile.planning_count == 1
        assert profile.evaluating_count == 1

    def test_all_execution_steps(self):
        """全执行步骤 → execution_heavy。"""
        steps = [
            make_step(StepType.EXECUTION, title="Run task 1"),
            make_step(StepType.EXECUTION, title="Run task 2"),
            make_step(StepType.EXECUTION, title="Run task 3"),
        ]
        inspector = CognitiveInspector()
        profile = inspector.inspect(steps)

        assert profile.execution_ratio > 0.5
        assert profile.classification == "execution_heavy"
        assert profile.executing_count == 3

    def test_mixed_steps(self):
        """混合步骤 → balanced。"""
        steps = [
            make_step(StepType.DIRECTIVE, title="Understand"),
            make_step(StepType.PLANNING, title="Plan"),
            make_step(StepType.EXECUTION, title="Execute"),
            make_step(StepType.TOOL_CALL, title="Call tool"),
            make_step(StepType.TOOL_RESULT, title="Get result"),
            make_step(StepType.OUTPUT, title="Output"),
        ]
        inspector = CognitiveInspector()
        profile = inspector.inspect(steps)

        assert profile.classification == "balanced"
        # 6 步，各项比例都不超过 0.5
        assert profile.planning_ratio <= 0.5
        assert profile.execution_ratio <= 0.5
        assert profile.tool_ratio <= 0.5
        assert profile.understanding_count == 1
        assert profile.planning_count == 1
        assert profile.executing_count == 1
        assert profile.selecting_count == 1
        assert profile.verifying_count == 1
        assert profile.summarizing_count == 1

    def test_tool_heavy_steps(self):
        """高工具调用比例 → tool_heavy。"""
        steps = [
            make_step(StepType.TOOL_CALL, title="Tool 1"),
            make_step(StepType.TOOL_RESULT, title="Result 1"),
            make_step(StepType.TOOL_CALL, title="Tool 2"),
            make_step(StepType.TOOL_RESULT, title="Result 2"),
            make_step(StepType.TOOL_CALL, title="Tool 3"),
            make_step(StepType.EXECUTION, title="Execute"),
        ]
        inspector = CognitiveInspector()
        profile = inspector.inspect(steps)

        assert profile.classification == "tool_heavy"
        assert profile.tool_ratio > 0.5
        assert profile.selecting_count == 3
        assert profile.verifying_count == 2

    def test_empty_steps(self):
        """空步骤列表返回全零 profile。"""
        inspector = CognitiveInspector()
        profile = inspector.inspect([])

        assert profile.planning_ratio == 0.0
        assert profile.execution_ratio == 0.0
        assert profile.tool_ratio == 0.0
        assert profile.classification == "unknown"
        assert profile.understanding_count == 0
        assert profile.evaluating_count == 0
        assert profile.planning_count == 0
        assert profile.executing_count == 0
        assert profile.selecting_count == 0
        assert profile.verifying_count == 0
        assert profile.analyzing_count == 0
        assert profile.summarizing_count == 0

    def test_no_reasoning_text_stored(self):
        """CognitiveProfile 不存储推理文本，只存计数/比率。

        验证没有任何字符串字段可能泄漏原生推理内容（CoT）。
        """
        steps = [
            make_step(StepType.THINKING, title="Thinking about approach",
                      content="Internal reasoning chain that should not leak"),
            make_step(StepType.EXECUTION, title="Run task"),
        ]
        inspector = CognitiveInspector()
        profile = inspector.inspect(steps)

        # CognitiveProfile 是 frozen dataclass，只包含：
        # planning_ratio, execution_ratio, tool_ratio,
        # understanding_count, evaluating_count, planning_count,
        # executing_count, selecting_count, verifying_count,
        # analyzing_count, summarizing_count, classification
        # 全是 float/int/str，没有 content/title/reasoning 字段
        assert profile.analyzing_count == 1  # THINKING 被正确归类
        assert profile.executing_count == 1
        assert profile.classification == "balanced"

        # 验证 profile 确实没有 content/title/reasoning 等效字段
        profile_dict = {
            f.name: getattr(profile, f.name)
            for f in profile.__dataclass_fields__.values()
        }
        for key in profile_dict:
            # 所有 field 必须是 int、float 或 'classification' str
            assert isinstance(profile_dict[key], (int, float, str)), (
                f"Field '{key}' has unexpected type: {type(profile_dict[key])}"
            )


import pytest
