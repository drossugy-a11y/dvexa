"""Runtime Intelligence Types — 智能分析层共享数据类型

所有 intelligence 模块的 DTO 定义。
纯数据结构，无业务逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
# Execution Analysis
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ExecutionAnalysisReport:
    """执行分析报告 — EventStore 历史聚合结果。

    纯分析输出，不可变。
    """
    total_traces: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    retry_rate: float = 0.0
    governance_block_rate: float = 0.0
    stage_durations: dict[str, float] = field(default_factory=dict)
    strategy_distribution: dict[str, int] = field(default_factory=dict)
    mode_distribution: dict[str, int] = field(default_factory=dict)
    error_types: dict[str, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════
# Failure Patterns
# ═══════════════════════════════════════════════════════════════════════


class FailurePatternType(str):
    REPEAT_FAILURE = "repeat_failure"
    FLAKY_PATH = "flaky_path"
    GOVERNANCE_BLOCK = "governance_block"
    ESCALATING_RISK = "escalating_risk"
    STALLED_RECOVERY = "stalled_recovery"
    RETRY_STORM = "retry_storm"


@dataclass(frozen=True)
class FailurePattern:
    """故障模式 — 由 FailurePatternEngine 检测。"""
    pattern_type: str
    severity: float  # 0.0 ~ 1.0
    trace_ids: tuple[str, ...]
    description: str
    suggestion: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Cognitive Profile
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CognitiveProfile:
    """认知执行统计 — 只存 counts/ratios，不存推理文本。"""
    planning_ratio: float = 0.0
    execution_ratio: float = 0.0
    tool_ratio: float = 0.0
    understanding_count: int = 0
    evaluating_count: int = 0
    planning_count: int = 0
    executing_count: int = 0
    selecting_count: int = 0
    verifying_count: int = 0
    analyzing_count: int = 0
    summarizing_count: int = 0
    classification: str = "unknown"  # planning_heavy | execution_heavy | tool_heavy | balanced


# ═══════════════════════════════════════════════════════════════════════
# Runtime Memory
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RuntimeMemoryTemplate:
    """运行时记忆模板 — 执行模式的 hash-based 指纹。"""
    fingerprint: str
    trace_id: str
    outcome: str  # success | failure
    duration_ms: float
    strategy: str
    mode: str
    stage_sequence: tuple[str, ...]
    match_count: int = 1


@dataclass(frozen=True)
class MemoryQueryResult:
    """记忆查询结果。"""
    exact_matches: list[RuntimeMemoryTemplate] = field(default_factory=list)
    partial_matches: list[RuntimeMemoryTemplate] = field(default_factory=list)
    total_indexed: int = 0
