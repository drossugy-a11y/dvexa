"""MCP Skill — MCP 协议能力（默认 disabled）

stateless: 每次调用独立子进程
no decision: 只转发 JSON-RPC 响应
no context: 不访问 task history / kernel state
"""

from tools.base_tool import Tool


class MCPSkill(Tool):
    """MCP 技能 — 封装 MCP 适配器的 stateless skill。

    默认 disabled，需在 mcp_servers.json 中启用。
    """

    def __init__(self, mcp_tool):
        self._mcp = mcp_tool

    def call(self, input_data) -> dict:
        return self._mcp.call(input_data)

    def cleanup(self):
        self._mcp.cleanup()
