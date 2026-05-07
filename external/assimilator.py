"""Capability Assimilator — 能力同化器（v1.88）

职责：
  1. 分析外部 agent 输出
  2. 识别可 skill 化的能力
  3. 生成能力摘要
  4. 输出治理建议

红线（绝对禁止）：
  - 自动 register_skill()
  - 自动修改 router
  - 自动修改 governor
  - 自动写入 capabilities/

Assimilator 只能生成"吞并建议"，不能真正吞并。

真正注册必须由：
  Human Confirm → Compiler → Manual Register
"""

from __future__ import annotations
from typing import Any


# Sandbox 输出中可被 assimilator 读取的安全字段
ALLOWED_INPUT_FIELDS = {"output", "artifacts", "logs", "metadata"}


class CapabilityAssimilator:
    """能力同化器 — 分析外部输出并生成吞并建议。

    注意：本类永不持有 router/governor 引用，确保无法自动注册。
    """

    def analyze(self, adapter_name: str, sandbox_output: dict) -> dict:
        """分析一次 sandbox 调用输出，生成吞并建议。

        Args:
            adapter_name: 外部 adapter 名称
            sandbox_output: ExternalSandbox.call() 的输出

        Returns:
            {
                "candidate_skill": {"name": str, "keywords": [str], "description": str},
                "confidence": float,       # 0.0~1.0，同化置信度
                "reason": str,             # 为什么认为可同化
                "risk": str,               # low / medium / high
                "source_project": str,     # adapter 来源标识
            }
            或 None（无可用能力）。
        """
        if not sandbox_output or not sandbox_output.get("output"):
            return None

        output = str(sandbox_output.get("output", ""))
        if not output.strip():
            return None

        suggestion = self._extract_suggestion(adapter_name, output)
        if suggestion:
            suggestion["source_project"] = adapter_name
        return suggestion

    def batch_analyze(self, calls: list[dict]) -> list[dict]:
        """批量分析多次 sandbox 调用。

        Args:
            calls: list of {"adapter_name": str, "sandbox_output": dict}

        Returns:
            list[dict] — 合并后的建议列表（按置信度降序）。
        """
        suggestions = []
        for call in calls:
            result = self.analyze(call["adapter_name"], call["sandbox_output"])
            if result:
                suggestions.append(result)

        suggestions.sort(key=lambda s: s.get("confidence", 0), reverse=True)
        return suggestions

    def _extract_suggestion(self, name: str, output: str) -> dict | None:
        """从输出文本中提取能力建议。

        当前使用简单的关键词 + 结构启发式。
        后续可接入 LLM 分析。
        """
        output_lower = output.lower()

        # 检测典型能力关键词
        domain_keywords = {
            "代码": ["def ", "class ", "import ", "函数", "return ", "python"],
            "网络": ["http", "https", "get ", "post ", "api", "curl", "请求"],
            "数据": ["data", "json", "csv", "数据库", "sql", "查询", "分析"],
            "文件": ["file", "read", "write", "open", "path", "目录"],
            "AI": ["model", "推理", "llm", "ai", "gpt", "生成", "embedding"],
        }

        detected = []
        for domain, kws in domain_keywords.items():
            if any(kw in output_lower for kw in kws):
                detected.append(domain)

        if not detected:
            return None

        confidence = min(0.3 + 0.15 * len(detected), 0.9)
        risk = "medium" if "AI" in detected or "代码" in detected else "low"
        keywords = detected + [f"external_{name}"]

        return {
            "candidate_skill": {
                "name": f"ext_{name}",
                "keywords": keywords,
                "description": f"从外部能力 {name} 提取: {'/'.join(detected)}",
            },
            "confidence": round(confidence, 2),
            "reason": f"检测到能力领域: {'/'.join(detected)} (基于 {len(detected)} 个匹配)",
            "risk": risk,
        }
