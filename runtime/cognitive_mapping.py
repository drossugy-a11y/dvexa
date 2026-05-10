"""Cognitive Stream Mapping v1 — StepType → Cognitive State/Label

将底层执行步骤映射为人类可读的认知状态和标签。
前端据此渲染认知流时间线。
"""

from __future__ import annotations

from runtime.step_events import StepType

# (cognitive_state, cognitive_label) 元组
CognitiveMap = dict[StepType, tuple[str, str]]

COGNITIVE_MAP: CognitiveMap = {
    StepType.DIRECTIVE:    ("understanding", "Understanding Request"),
    StepType.GOVERNANCE:   ("evaluating",    "Evaluating Safety Constraints"),
    StepType.PLANNING:     ("planning",      "Preparing Execution Strategy"),
    StepType.EXECUTION:    ("executing",     "Executing Task Pipeline"),
    StepType.TOOL_CALL:    ("selecting",     "Selecting Runtime Capability"),
    StepType.TOOL_RESULT:  ("verifying",     "Processing Tool Results"),
    StepType.THINKING:     ("analyzing",     "Reasoning About Approach"),
    StepType.MEMORY:       ("summarizing",   "Updating System Memory"),
    StepType.OUTPUT:       ("summarizing",   "Finalizing Response"),
    StepType.COMPLETE:     ("completed",     "Task Complete"),
    StepType.ERROR:        ("completed",     "Error Encountered"),
    StepType.BLOCKED:      ("evaluating",    "Execution Blocked by Policy"),
    StepType.RECOVERY:     ("analyzing",     "Attempting Automatic Recovery"),
}


def get_cognitive(step_type: StepType) -> tuple[str, str]:
    """获取步骤类型对应的认知状态和标签。"""
    return COGNITIVE_MAP.get(step_type, ("processing", "Processing"))
