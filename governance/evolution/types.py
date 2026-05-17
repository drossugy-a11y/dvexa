"""Evolution Types — 演化建议与闸门判定数据类型

所有 evolution 模块的 DTO 定义。
Suggestion 不能自动 apply，必须经过 EvolutionGate。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvolutionSuggestion:
    """演化建议 — 只能建议，不能自动应用。"""
    target: str          # strategy | capability | threshold | route
    proposed_change: str
    confidence: float    # 0.0 ~ 1.0
    evidence: tuple[str, ...]  # 相关 trace_id 列表
    description: str = ""


@dataclass(frozen=True)
class GateCheckResult:
    """单次闸门检查结果。"""
    check_name: str   # health | drift | rollback | benchmark
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class EvolutionVerdict:
    """演化闸门判定 — 四个检查的综合结果。"""
    suggestion_id: str
    passed_checks: tuple[GateCheckResult, ...] = field(default_factory=tuple)
    failed_checks: tuple[GateCheckResult, ...] = field(default_factory=tuple)

    @property
    def allowed(self) -> bool:
        return len(self.failed_checks) == 0

    @property
    def summary(self) -> str:
        if self.allowed:
            return "PASS"
        failed_names = ", ".join(c.check_name for c in self.failed_checks)
        return f"BLOCKED: {failed_names}"
