"""CognitiveInspector v1 — 运行时认知剖面分析

分析 RuntimeStep 序列，生成 CognitiveProfile。
只统计计数/比率，不存储推理文本。
"""

from __future__ import annotations

from runtime.cognitive_mapping import COGNITIVE_MAP
from runtime.intelligence.types import CognitiveProfile
from runtime.step_events import RuntimeStep, StepType


class CognitiveInspector:
    """认知检查器 — 分析执行步骤序列的认知特征。"""

    def inspect(self, steps: list[RuntimeStep]) -> CognitiveProfile:
        """分析步骤序列，生成认知剖面。

        使用 COGNITIVE_MAP 将 StepType 映射为 8 种认知活动：
        - understanding:  DIRECTIVE 步骤
        - evaluating:     GOVERNANCE, BLOCKED 步骤
        - planning:       PLANNING 步骤
        - executing:      EXECUTION 步骤
        - selecting:      TOOL_CALL 步骤
        - verifying:      TOOL_RESULT 步骤
        - analyzing:      THINKING, RECOVERY 步骤
        - summarizing:    MEMORY, OUTPUT 步骤

        Args:
            steps: RuntimeStep 列表。

        Returns:
            CognitiveProfile（无推理文本，只存计数和比率）。
        """
        if not steps:
            return CognitiveProfile()

        # 计数 8 种认知活动
        understanding_count = 0  # DIRECTIVE
        evaluating_count = 0  # GOVERNANCE, BLOCKED
        planning_count = 0  # PLANNING
        executing_count = 0  # EXECUTION
        selecting_count = 0  # TOOL_CALL
        verifying_count = 0  # TOOL_RESULT
        analyzing_count = 0  # THINKING, RECOVERY
        summarizing_count = 0  # MEMORY, OUTPUT

        for step in steps:
            st = step.step_type
            if st == StepType.DIRECTIVE:
                understanding_count += 1
            elif st in (StepType.GOVERNANCE, StepType.BLOCKED):
                evaluating_count += 1
            elif st == StepType.PLANNING:
                planning_count += 1
            elif st == StepType.EXECUTION:
                executing_count += 1
            elif st == StepType.TOOL_CALL:
                selecting_count += 1
            elif st == StepType.TOOL_RESULT:
                verifying_count += 1
            elif st in (StepType.THINKING, StepType.RECOVERY):
                analyzing_count += 1
            elif st in (StepType.MEMORY, StepType.OUTPUT):
                summarizing_count += 1

        total = len(steps)

        # 比率计算
        planning_ratio = (
            (planning_count + understanding_count) / total if total > 0 else 0.0
        )
        execution_ratio = executing_count / total if total > 0 else 0.0
        tool_ratio = (
            (selecting_count + verifying_count) / total if total > 0 else 0.0
        )

        # 分类
        if planning_ratio > 0.5:
            classification = "planning_heavy"
        elif execution_ratio > 0.5:
            classification = "execution_heavy"
        elif tool_ratio > 0.5:
            classification = "tool_heavy"
        else:
            classification = "balanced"

        return CognitiveProfile(
            planning_ratio=round(planning_ratio, 4),
            execution_ratio=round(execution_ratio, 4),
            tool_ratio=round(tool_ratio, 4),
            understanding_count=understanding_count,
            evaluating_count=evaluating_count,
            planning_count=planning_count,
            executing_count=executing_count,
            selecting_count=selecting_count,
            verifying_count=verifying_count,
            analyzing_count=analyzing_count,
            summarizing_count=summarizing_count,
            classification=classification,
        )
