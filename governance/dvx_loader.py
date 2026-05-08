"""DVX Language v0.1 — 结构化治理输入解析器

DVX 是 DVexa 的结构化输入语言，格式为：
    ACTION <target> { intent: "...", mode: "...", constraint: "...", output: "..." }

定位：位于治理流水线最前端，将原始输入解析为结构化 ACTION 格式。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ─── Types ─────────────────────────────────────────────────────────────────────

@dataclass
class DVXAction:
    """解析后的 DVX Action。

    Attributes:
        target: 操作目标（模块/组件名称）
        intent: 操作意图
        mode: 分析模式
        constraint: 约束描述（可选）
        output: 预期输出描述（可选）
        warnings: 验证警告列表
        raw: 原始输入文本
    """
    target: str
    intent: str = "analysis"
    mode: str = "observe"
    constraint: str | None = None
    output: str | None = None
    warnings: list[str] = field(default_factory=list)
    raw: str = ""


# ─── Patterns ──────────────────────────────────────────────────────────────────

_ACTION_PATTERN = re.compile(
    r'ACTION\s+(\S+)\s*\{'
    r'(.*?)\}',
    re.DOTALL,
)

_FIELD_PATTERN = re.compile(
    r'(intent|mode|constraint|output)\s*:\s*"([^"]*)"',
)


# ─── Parser ────────────────────────────────────────────────────────────────────

class DVXLoader:
    """DVX 语言解析器 — 将 ACTION 格式文本解析为结构化 DVXAction。"""

    VALID_INTENTS = {"analysis", "execution", "manipulation", "extraction", "unknown"}
    VALID_MODES = {"observe", "strict", "simulate"}

    def parse(self, text: str) -> DVXAction:
        """解析单个 ACTION 块。

        Args:
            text: 包含 ACTION 格式的输入文本。

        Returns:
            DVXAction: 解析结果，含验证警告。

        Raises:
            DVXParseError: 文本不包含有效的 ACTION 块。
        """
        if not text or not text.strip():
            raise DVXParseError("Empty input: no ACTION block found")

        match = _ACTION_PATTERN.search(text)
        if not match:
            raise DVXParseError(
                "No valid ACTION block found. Expected format: "
                "ACTION <target> { intent: \"...\", mode: \"...\" }"
            )

        target = match.group(1).strip()
        body = match.group(2).strip()

        if not target:
            raise DVXParseError("ACTION target must not be empty")

        # Parse fields from body
        fields: dict[str, str] = {}
        for key, value in _FIELD_PATTERN.findall(body):
            fields[key] = value

        action = DVXAction(
            target=target,
            intent=fields.get("intent", "analysis"),
            mode=fields.get("mode", "observe"),
            constraint=fields.get("constraint"),
            output=fields.get("output"),
            raw=text.strip(),
        )

        # Validate
        self.validate(action)

        return action

    def parse_multi(self, text: str) -> list[DVXAction]:
        """解析文本中包含的多个 ACTION 块。

        每个 ACTION 块独立解析，一个失败不影响其他。

        Args:
            text: 可能包含多个 ACTION 块的文本。

        Returns:
            list[DVXAction]: 成功解析的 ACTION 列表。
        """
        if not text or not text.strip():
            return []

        results: list[DVXAction] = []
        for match in _ACTION_PATTERN.finditer(text):
            try:
                action = self.parse(match.group(0))
                results.append(action)
            except DVXParseError:
                continue  # 跳过无效块

        return results

    def is_action(self, text: str) -> bool:
        """检查文本是否包含有效的 ACTION 格式。"""
        if not text or not text.strip():
            return False
        match = _ACTION_PATTERN.search(text)
        if not match:
            return False
        target = match.group(1).strip()
        return bool(target)

    def validate(self, action: DVXAction) -> DVXAction:
        """验证已解析的字段值合法性。添加警告但不修改功能值。"""
        original = action  # keep reference for attribute access

        # intent validation
        if original.intent not in self.VALID_INTENTS:
            action.warnings.append(
                f"Invalid intent '{original.intent}', "
                f"fallback to 'unknown'"
            )
            action.intent = "unknown"

        # mode validation
        if original.mode not in self.VALID_MODES:
            action.warnings.append(
                f"Invalid mode '{original.mode}', "
                f"fallback to 'observe'"
            )
            action.mode = "observe"

        return action


# ─── Exceptions ────────────────────────────────────────────────────────────────

class DVXError(Exception):
    """DVX 语言基类异常。"""
    pass


class DVXParseError(DVXError):
    """解析错误 — 输入不是有效的 ACTION 格式。"""
    pass
