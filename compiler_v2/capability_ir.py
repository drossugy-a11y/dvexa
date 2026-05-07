"""Capability IR v2.0 — 统一中间表示

核心数据结构：
  CapabilitySignal  — 从事件提取的能力信号
  CapabilityNode    — IR 中的单个能力节点
  CapabilityIR      — 完整中间表示
  CapabilityStep    — DXB 中的单个执行步骤
  DXB               — DVX Execution Blueprint
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# CapabilitySignal — 从 Event 提取的能力信号
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilitySignal:
    """从事件或外部源提取的能力信号。

    每个 Event 中可以提取多个 signal。
    """
    source: str
    signal_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    trace_id: str = ""


# ═══════════════════════════════════════════════════════════════════
# CapabilityNode — IR 中的单个能力节点
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityNode:
    """能力图谱中的一个节点。

    类型: SKILL | TOOL | GOVERNANCE_CHECK | RUNTIME_ACTION | MEMORY
    """
    id: str
    node_type: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_governance(self) -> bool:
        return self.node_type == "GOVERNANCE_CHECK"

    @property
    def is_skill(self) -> bool:
        return self.node_type == "SKILL"


# ═══════════════════════════════════════════════════════════════════
# CapabilityIR — 完整中间表示
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CapabilityIR:
    """编译中间表示 — 从事件流提取的能力结构快照。"""
    intent: str = ""
    target: str = ""
    capabilities: list[CapabilityNode] = field(default_factory=list)
    risk_signals: dict[str, float] = field(default_factory=dict)
    governance_constraints: dict[str, Any] = field(default_factory=dict)
    extracted_patterns: list[str] = field(default_factory=list)
    trace_id: str = ""

    def capability_count(self) -> int:
        return len(self.capabilities)

    def node_ids_by_type(self, node_type: str) -> list[str]:
        return [n.id for n in self.capabilities if n.node_type == node_type]


# ═══════════════════════════════════════════════════════════════════
# CapabilityStep — DXB 中的单个执行步骤
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapabilityStep:
    """DXB 中的单个执行步骤。

    Kernel 按顺序执行每个 Step，不做决策。
    """
    id: str
    step_type: str
    capability_ref: str
    inputs: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    risk: float = 0.0
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    expected_output: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# DXB — DVX Execution Blueprint
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DXB:
    """DVX Execution Blueprint — 编译器的最终输出。

    Kernel v2 只负责按 DXB 的顺序执行，不做任何决策。
    """
    id: str
    steps: list[CapabilityStep] = field(default_factory=list)
    dag: dict[str, list[str]] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    origin_trace_id: str = ""
    compiled_at: float = 0.0

    def __post_init__(self):
        if not self.compiled_at:
            self.compiled_at = time.time()
        if not self.dag and self.steps:
            self._build_dag()

    def _build_dag(self) -> None:
        """从 steps 的 dependencies 构建 DAG。"""
        dag: dict[str, list[str]] = {}
        for step in self.steps:
            dag[step.id] = list(step.dependencies)
        self.dag = dag

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def risk_score(self) -> float:
        if not self.steps:
            return 0.0
        return max(s.risk for s in self.steps)

    def get_step(self, step_id: str) -> CapabilityStep | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def ordered_steps(self) -> list[CapabilityStep]:
        """按 DAG 拓扑序返回步骤列表。"""
        if not self.steps:
            return []
        order = _topological_sort(self.dag)
        step_map = {s.id: s for s in self.steps}
        return [step_map[sid] for sid in order if sid in step_map]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "origin_trace_id": self.origin_trace_id,
            "compiled_at": self.compiled_at,
            "step_count": self.step_count,
            "risk_score": self.risk_score,
            "constraints": self.constraints,
            "dag": self.dag,
            "steps": [
                {
                    "id": s.id,
                    "type": s.step_type,
                    "capability_ref": s.capability_ref,
                    "inputs": s.inputs,
                    "dependencies": s.dependencies,
                    "risk": s.risk,
                    "preconditions": s.preconditions,
                    "postconditions": s.postconditions,
                }
                for s in self.steps
            ],
        }


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def _topological_sort(dag: dict[str, list[str]]) -> list[str]:
    """DAG 拓扑排序（Kahn 算法）。"""
    in_degree: dict[str, int] = {n: 0 for n in dag}
    for node, deps in dag.items():
        for dep in deps:
            in_degree[node] = in_degree.get(node, 0) + 1
            if dep not in in_degree:
                in_degree[dep] = 0

    queue = [n for n, d in in_degree.items() if d == 0]
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for other, deps in dag.items():
            if node in deps:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)

    return result
