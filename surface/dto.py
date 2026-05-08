"""DVX Surface Data Transfer Objects — 系统快照 DTO 定义"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SystemSnapshot:
    """全量系统快照 — 一次性聚合所有子系统状态。"""
    timestamp: str = ""
    task_count: int = 0
    system_health: str = "unknown"
    capability_summary: dict[str, Any] = field(default_factory=dict)
    evolution_report: dict[str, Any] = field(default_factory=dict)
    governance_status: dict[str, Any] = field(default_factory=dict)
    execution_history: list[dict[str, Any]] = field(default_factory=list)
    insight_report: dict[str, Any] = field(default_factory=dict)
    metric_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapabilityNodeDTO:
    """能力节点 — 用于前端 DAG 可视化。"""
    id: str
    name: str
    category: str
    subcategory: str
    maturity: str
    risk_level: str
    usage_count: int = 0
    success_rate: float = 0.0


@dataclass
class GraphEdgeDTO:
    """依赖边 — 用于前端 DAG 可视化。"""
    source: str
    target: str
    type: str = "depends_on"


@dataclass
class GovernanceStatusDTO:
    """治理状态摘要。"""
    health_score: float = 0.0
    health_status: str = "unknown"
    permission_mode: str = "FROZEN"
    can_optimize: bool = False
    drift_detected: bool = False
    lock_active: bool = False
    signals: list[str] = field(default_factory=list)
    process_count: int = 0


@dataclass
class ExecutionEventDTO:
    """执行事件 — 用于时间线展示。"""
    task_id: str = ""
    status: str = ""
    summary: str = ""
    timestamp: str = ""
    retry_count: int = 0
