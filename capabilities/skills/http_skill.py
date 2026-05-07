"""HTTP Skill — 网络请求能力

stateless: 每次请求独立
no decision: 只转发响应，不做判断
"""

from tools.base_tool import Tool


class HTTPSkill(Tool):
    """HTTP 请求技能 — 封装 HTTP 调用的 stateless skill。"""

    def __init__(self, http_tool):
        self._http = http_tool

    def call(self, input_data) -> dict:
        return self._http.call(input_data)
