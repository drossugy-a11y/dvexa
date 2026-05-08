"""Tool Policy — 能力访问策略治理

提取自 OpenClaw tool_policy.py 的 Allow/Deny 双列表 + 优先级链模式。
DVexa 适配：静态工具组定义，无动态导入，纯函数无状态。

核心思想：
  1. Deny 优先检查（黑名单优先级 > 白名单）
  2. 空 Allow = 允许全部（仅受 Deny 约束）
  3. Glob 模式匹配（fnmatch）
  4. 三层优先级：skill-specific → global → defaults
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Literal


# ─── 工具组静态定义 ──────────────────────────────────────────────────

TOOL_GROUPS: dict[str, list[str]] = {
    "all": ["llm", "code", "http", "github", "security"],
    "coding": ["code"],
    "readonly": ["llm", "http", "github", "security"],
    "safe": ["llm", "http"],
    "network": ["http", "github"],
    "analyze": ["llm", "security"],
}

# ─── 默认策略 ────────────────────────────────────────────────────────

DEFAULT_DENY: list[str] = []
DEFAULT_ALLOW: list[str] = []  # 空 = 允许所有（Deny 优先）


@dataclass
class ToolPolicy:
    """工具访问策略。

    Attributes:
        allow: 允许列表（空列表 = 允许所有）
        deny:  拒绝列表（优先于 allow）
    """
    allow: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOW))
    deny: list[str] = field(default_factory=lambda: list(DEFAULT_DENY))


# ─── 核心函数 ────────────────────────────────────────────────────────


def expand_tool_list(tool_list: list[str]) -> list[str]:
    """展开工具组名为具体工具名。

    例如 ["all"] → ["llm", "code", "http", "github", "security"]
    不在组中的名称保持原样。
    """
    result: list[str] = []
    for name in tool_list:
        expanded = TOOL_GROUPS.get(name)
        if expanded is not None:
            result.extend(expanded)
        else:
            result.append(name)
    return result


def _normalize(name: str) -> str:
    return name.strip().lower()


def is_tool_allowed(policy: ToolPolicy, tool_name: str) -> bool:
    """判断工具是否被允许。

    Deny 列表优先检查，然后 Allow 列表兜底。
    空 Allow = 允许所有（只要不在 Deny 中）。

    Args:
        policy: 工具访问策略
        tool_name: 工具名

    Returns:
        True 如果工具被允许
    """
    normalized = _normalize(tool_name)

    # Deny 优先检查
    denied = expand_tool_list(policy.deny)
    for pattern in denied:
        if fnmatch.fnmatch(normalized, _normalize(pattern)):
            return False

    # 空 Allow = 允许全部
    allowed = expand_tool_list(policy.allow)
    if not allowed:
        return True

    for pattern in allowed:
        if fnmatch.fnmatch(normalized, _normalize(pattern)):
            return True

    return False


def resolve_policy(
    skill_specific: ToolPolicy | None = None,
    global_policy: ToolPolicy | None = None,
) -> ToolPolicy:
    """解析三层优先级策略。

    优先级: skill_specific > global > defaults
    每层仅覆盖非空字段。

    Args:
        skill_specific: skill 级策略（最高优先级）
        global_policy: 全局策略（中间优先级）

    Returns:
        合并后的 ToolPolicy
    """
    allow = list(DEFAULT_ALLOW)
    deny = list(DEFAULT_DENY)

    if global_policy is not None:
        if global_policy.allow:
            allow = global_policy.allow
        if global_policy.deny:
            deny = global_policy.deny

    if skill_specific is not None:
        if skill_specific.allow:
            allow = skill_specific.allow
        if skill_specific.deny:
            deny = skill_specific.deny

    return ToolPolicy(allow=allow, deny=deny)


def default_policy() -> ToolPolicy:
    """返回默认策略（允许所有）。"""
    return ToolPolicy()


def restricted_policy(allowed_only: list[str] | None = None) -> ToolPolicy:
    """创建受限策略，仅允许指定工具。"""
    return ToolPolicy(
        allow=allowed_only or [],
        deny=[],
    )
