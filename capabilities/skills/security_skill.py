"""Security Skill — 安全扫描能力

stateless: 每次请求独立扫描
no decision: 只返回匹配结果，不做安全判断
no self modify: 纯只读分析

包装 SecurityScannerTool，提供安全代码扫描能力。
提取自 OpenClaw skill_scanner.py 的 7 类危险模式设计。
"""

from tools.base_tool import Tool


class SecuritySkill(Tool):
    """安全扫描 Skill — 对代码进行 7 类危险模式分析。

    输入:
      {"action": "scan_text", "text": "...", "source": "optional_path"}
      {"action": "scan_file", "path": "/path/to/file"}
      {"action": "rules"}
    """

    def __init__(self, scanner_tool):
        self._scanner = scanner_tool

    def call(self, input_data) -> dict:
        return self._scanner.call(input_data)
