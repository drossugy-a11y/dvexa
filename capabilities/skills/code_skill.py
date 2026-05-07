"""Code Skill — 代码执行能力

stateless: 每次执行独立 sandbox
no decision: 只执行代码，不做判断
"""

from tools.base_tool import Tool


class CodeSkill(Tool):
    """代码执行技能 — 封装 Python 代码执行的 stateless skill。"""

    def __init__(self, code_tool):
        self._code = code_tool

    def call(self, input_data) -> dict:
        return self._code.call(input_data)
