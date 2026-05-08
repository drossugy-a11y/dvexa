"""Capability Taxonomy v1.0 — 能力分类学核心模型

DVexa 的能力文明地图。只负责描述和追踪，不负责执行。

设计红线:
  - deterministic
  - append-only evolution history
  - 不修改 frozen layer
  - 不接管 execution runtime
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MaturityLevel(str, Enum):
    EXPERIMENTAL = "experimental"
    ACTIVE = "active"
    STABLE = "stable"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    RECOVERED = "recovered"
    REMOVED = "removed"


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceType(str, Enum):
    SKILL = "skill"
    TOOL = "tool"
    GOVERNANCE = "governance"
    PATTERN = "pattern"
    ASSIMILATION = "assimilation"
    OPTIMIZATION = "optimization"
    RUNTIME = "runtime"
    EXTERNAL = "external"


class LifecycleState(str, Enum):
    REGISTERED = "registered"
    VALIDATED = "validated"
    ACTIVE = "active"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    RECOVERED = "recovered"
    RETIRED = "retired"


@dataclass
class CapabilityNode:
    capability_id: str
    name: str
    category: str
    subcategory: str

    description: str

    maturity: str = MaturityLevel.EXPERIMENTAL.value
    risk_level: str = RiskLevel.LOW.value

    source: str = ""
    source_type: str = ""

    dependencies: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    related_patterns: list[str] = field(default_factory=list)

    governance_approved: bool = False

    lifecycle_state: str = LifecycleState.REGISTERED.value

    usage_count: int = 0
    success_rate: float = 1.0

    evolution_history: list[dict[str, Any]] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


# ─── 默认能力分类树 ──────────────────────────────────────────────────────────
# 6 大类 27 子类

TAXONOMY_TREE: dict[str, dict[str, list[str] | str]] = {
    "planning": {
        "label": "Planning",
        "description": "任务规划与策略选择能力",
        "subcategories": [
            "decomposition",
            "replanning",
            "reflection",
            "strategy-selection",
            "goal-abstraction",
        ],
    },
    "execution": {
        "label": "Execution",
        "description": "任务执行与工具路由能力",
        "subcategories": [
            "tool-routing",
            "retry",
            "sandbox-execution",
            "async-workflow",
            "workflow-orchestration",
            "streaming",
        ],
    },
    "memory": {
        "label": "Memory",
        "description": "记忆存储与上下文管理能力",
        "subcategories": [
            "episodic-memory",
            "execution-trace",
            "replay",
            "context-compression",
            "persistent-state",
            "structured-messages",
        ],
    },
    "governance": {
        "label": "Governance",
        "description": "治理决策与策略控制能力",
        "subcategories": [
            "policy",
            "stabilization",
            "rollback",
            "drift-detection",
            "optimization-control",
            "meta-control",
        ],
    },
    "assimilation": {
        "label": "Assimilation",
        "description": "外部能力吞并与模式提取能力",
        "subcategories": [
            "repo-analysis",
            "pattern-extraction",
            "governance-review",
            "sandbox-injection",
            "regression-validation",
        ],
    },
    "optimization": {
        "label": "Optimization",
        "description": "系统自优化与效率分析能力",
        "subcategories": [
            "cost-model",
            "complexity-budget",
            "global-optimization",
            "efficiency-analysis",
            "convergence-control",
        ],
    },
}


def build_default_taxonomy() -> dict[str, list[str]]:
    """构建默认分类树（category → subcategories）。"""
    return {cat: list(info["subcategories"]) for cat, info in TAXONOMY_TREE.items()}


def category_description(category: str) -> str:
    entry = TAXONOMY_TREE.get(category, {})
    return entry.get("description", "")


def valid_subcategory(category: str, subcategory: str) -> bool:
    entry = TAXONOMY_TREE.get(category)
    if not entry:
        return False
    return subcategory in entry["subcategories"]
