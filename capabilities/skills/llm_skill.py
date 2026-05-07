"""LLM Skill — 通用 AI 能力

stateless: 每次调用独立，不记忆上下文
no decision: 只转发 prompt，不做判断
"""

from tools.base_tool import Tool


class LLMSkill(Tool):
    """LLM 技能 — 封装 LLM 调用的 stateless skill。"""

    def __init__(self, llm_tool):
        self._llm = llm_tool

    def call(self, input_data) -> dict:
        return self._llm.call(input_data)
