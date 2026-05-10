"""LLM Tool — 统一 LLM 调用接口

所有 LLM 调用必须经过此工具。
Runtime Persona Kernel 在此注入系统级身份声明。
"""

from __future__ import annotations

from tools.base_tool import Tool
from openai import OpenAI


class LLMTool(Tool):
    """LLM 调用工具 — 所有模型请求的最终边界。

    在 call() 中强制注入 runtime_persona，
    确保所有 LLM 调用都携带正确的运行时身份。
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self._runtime_persona: str | None = None

    def set_runtime_persona(self, persona: str) -> None:
        """设置运行时身份声明。

        此声明在 call() 中 **总是** 优先于任何其他 system_prompt。
        用户输入无法覆盖。
        """
        self._runtime_persona = persona

    def clear_runtime_persona(self) -> None:
        """清除运行时身份（仅在重置时使用）。"""
        self._runtime_persona = None

    def call(self, prompt: str, system_prompt: str | None = None) -> dict:
        """调用 LLM。

        Runtime persona 总是作为第一条 system message 注入，
        保证身份声明优先级最高。
        """
        messages = []

        # ── 强制注入 runtime persona（最先、最高优先级） ────────────
        effective_system = ""
        if self._runtime_persona:
            effective_system = self._runtime_persona
        if system_prompt:
            if effective_system:
                effective_system += "\n\n"
            effective_system += system_prompt

        if effective_system:
            messages.append({"role": "system", "content": effective_system})

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        content = response.choices[0].message.content
        return {"content": content, "model": self.model}
