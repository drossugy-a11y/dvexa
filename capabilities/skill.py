"""Skill Definition — 技能定义与注册中心

每个 skill 必须满足：
  - stateless：无状态，不存储上下文
  - input → output：纯函数式 IO
  - no memory：不记忆历史
  - no decision：不做判断
"""

from __future__ import annotations
from typing import Callable, Protocol


class SkillHandler(Protocol):
    """技能处理器协议 — 所有 skill 必须实现此接口"""
    def call(self, input_data: str) -> dict: ...


class SkillDef:
    """技能定义 — 不可变的能力单元"""

    def __init__(self, name: str, handler: SkillHandler, keywords: list[str] | None = None, description: str = ""):
        self.name = name
        self.handler = handler
        self.keywords = keywords or []
        self.description = description


class SkillRegistry:
    """技能注册中心 — 管理所有能力的注册和发现

    这是 Capability Layer 的核心入口。
    所有能力必须通过 registry 注册，才能被系统使用。
    """

    def __init__(self):
        self._skills: dict[str, SkillDef] = {}
        self._keyword_map: dict[str, list[str]] = {}  # keyword → [skill_names]

    def register(self, name: str, handler: SkillHandler, keywords: list[str] | None = None, description: str = ""):
        """注册一个技能。

        Args:
            name: 技能唯一标识（如 "code", "llm", "http"）
            handler: 技能处理器（实现 call(input) → dict）
            keywords: 触发关键词列表（用于 route 匹配）
            description: 技能描述
        """
        skill = SkillDef(name, handler, keywords, description)
        self._skills[name] = skill
        for kw in (keywords or []):
            key = kw.lower()
            if key not in self._keyword_map:
                self._keyword_map[key] = []
            self._keyword_map[key].append(name)

    def get(self, name: str) -> SkillDef | None:
        return self._skills.get(name)

    def match(self, action: str) -> str | None:
        """根据 action 文本匹配技能名。

        纯关键词匹配，不做推理，不做判断。
        返回第一个匹配技能名。
        """
        action_lower = action.lower()
        for kw, skill_names in self._keyword_map.items():
            if kw in action_lower:
                return skill_names[0]
        return None

    def match_all(self, action: str) -> list[str]:
        """根据 action 文本匹配所有相关技能名，用于 governance 评分排序。"""
        action_lower = action.lower()
        matched: set[str] = set()
        for kw, skill_names in self._keyword_map.items():
            if kw in action_lower:
                matched.update(skill_names)
        return list(matched)

    def all_skills(self) -> dict[str, SkillDef]:
        return dict(self._skills)

    @property
    def count(self) -> int:
        return len(self._skills)
