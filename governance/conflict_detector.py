"""Conflict Detector — 能力冲突检测

解决以下问题：
  - 重复 skill（相同功能不同名）
  - 功能重叠（关键词高度相似）
  - MCP vs Tool 冲突
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SkillConflict:
    skill_a: str
    skill_b: str
    similarity: float
    overlap_keywords: list[str] = field(default_factory=list)


SIMILARITY_THRESHOLD = 0.85


class ConflictDetector:
    """冲突检测器 — 检查能力之间的功能重叠。"""

    def detect_all(self, skills: dict) -> list[SkillConflict]:
        """检测所有已注册 skill 之间的冲突。

        Args:
            skills: dict[name, SkillDef]

        Returns:
            冲突列表
        """
        conflicts = []
        names = list(skills.keys())

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                conflict = self._check_pair(skills[names[i]], skills[names[j]])
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _check_pair(self, skill_a, skill_b) -> SkillConflict | None:
        """检查一对 skill 之间的冲突。"""
        kw_a = set(k.lower() for k in (skill_a.keywords or []))
        kw_b = set(k.lower() for k in (skill_b.keywords or []))

        if not kw_a or not kw_b:
            return None

        overlap = kw_a & kw_b
        if not overlap:
            return None

        similarity = len(overlap) / max(len(kw_a | kw_b), 1)

        if similarity >= SIMILARITY_THRESHOLD:
            return SkillConflict(
                skill_a=skill_a.name,
                skill_b=skill_b.name,
                similarity=round(similarity, 3),
                overlap_keywords=sorted(overlap),
            )

        return None
