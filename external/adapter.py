"""External Agent Adapter Protocol — 外部能力接入协议（v1.88）

所有外部 agent 必须实现此 Protocol。

约束：
  - stateless（无状态）
  - no memory write（禁止写入 memory）
  - no kernel access（禁止访问 kernel）
  - no governance access（禁止访问 governance）
  - no planner access（禁止访问 planner）
  - input → output only（仅输入输出转换）
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class ExternalAgentAdapter(Protocol):
    """外部 agent 适配器协议。

    实现此协议的类可被 ExternalSandbox 安全调用。
    """

    def name(self) -> str:
        """返回外部 agent 名称。"""
        ...

    def capabilities(self) -> list[str]:
        """返回能力列表。"""
        ...

    def execute(self, task: str) -> dict:
        """执行任务并返回结果。

        Returns:
            dict: 必须包含 "output" 键，可选 "artifacts"/"logs"/"metadata"。
            禁止返回: confidence, score, decision, status, routing, governance, suggestion
        """
        ...

    def metadata(self) -> dict:
        """返回元信息（版本、作者、依赖等）。"""
        ...
