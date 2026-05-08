"""DVXRuntimeModel v1.91 — Event-Sourced 运行时数据模型

Event = 系统中唯一的事实结构。
RuntimeContext = 轻量上下文（当前输入/输出/元数据）。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ExecutionStage(enum.Enum):
    """运行时执行阶段枚举。"""
    LOAD = "load"
    SEMANTIC = "semantic"
    VALIDATE = "validate"
    SCHEDULE = "schedule"
    GOVERN = "govern"
    LOG = "log"


class DecisionNode(enum.Enum):
    """流水线中的决策节点枚举。"""
    SGL_GOVERNANCE = "sgl_governance"
    ATS_VERDICT = "ats_verdict"
    SCHEDULER_DECISION = "scheduler_decision"


# ── 向下兼容保留 ──────────────────────────────────────────────────────────

@dataclass
class TraceEvent:
    """（已弃用 — 由 runtime.event.Event 替代）

    保留以供旧代码引用，新代码使用 runtime.event.Event。
    """
    stage: ExecutionStage
    input_snapshot: Any
    output_snapshot: Any
    decision_reason: str = ""
    risk_score: float = 0.0
    timestamp: str = ""
    latency_s: float = 0.0
    status: str = "ok"


@dataclass
class GovernanceSnapshot:
    """治理层快照。"""
    skill_count: int = 0
    quarantined_count: int = 0
    ecosystem_stability: float = 1.0
    churn_rate: float = 0.0
    skill_statuses: dict[str, str] = field(default_factory=dict)
    global_policy_allow: list[str] = field(default_factory=list)
    global_policy_deny: list[str] = field(default_factory=list)


# ── 新 RuntimeContext ────────────────────────────────────────────────────

@dataclass
class RuntimeContext:
    """运行时上下文 — 轻量级当前执行状态容器。

    只保留：
      - 当前输入
      - 事件引用（来自 EventStore）
      - trace_id / 元数据

    不再存储历史数据或独立 report/dict。
    所有历史通过 EventStore.project() 获取。
    """
    # 输入
    input: str = ""

    # 事件列表（同一 trace 的全量事件，Engine.run() 过程中构造）
    events: list = field(default_factory=list)

    # 元数据
    trace_id: str = ""
    timestamp: str = ""
    total_latency_s: float = 0.0
    overall_status: str = "pending"

    @property
    def last_event(self):
        """最后一个事件（当前阶段输出）。"""
        return self.events[-1] if self.events else None

    @property
    def passed(self) -> bool:
        """整体是否通过 — 从事件中推导。"""
        if self.overall_status != "complete":
            return False
        for e in reversed(self.events):
            if e.stage == "schedule" and e.event_type == "decision":
                fs = e.payload.get("final_state", "")
                return fs in ("approved", "logged", "next", "ready")
        return False

    @property
    def risk_score(self) -> float:
        """全链路风险评分 — 取事件中风险最大值。"""
        scores = [0.0]
        for e in self.events:
            if e.event_type == "risk" and "risk_score" in e.payload:
                scores.append(e.payload["risk_score"])
        return max(scores)

    # ── 向下兼容属性（从事件投影） ──────────────────────────────────────

    @property
    def execution_trace(self):
        """（已弃用）保持旧接口兼容。"""
        from runtime.event import Event
        return [e for e in self.events if isinstance(e, Event)]

    @property
    def dvx_action(self) -> dict:
        for e in reversed(self.events):
            if e.stage == "load":
                return e.payload
        return {}

    @property
    def sgl_result(self) -> dict:
        for e in reversed(self.events):
            if e.stage == "semantic":
                return e.payload
        return {}

    @property
    def ats_result(self) -> dict:
        for e in reversed(self.events):
            if e.stage == "validate":
                return e.payload
        return {}

    @property
    def scheduler_decision(self) -> dict:
        for e in reversed(self.events):
            if e.stage == "schedule" and e.event_type == "decision":
                return e.payload
        return {}

    @property
    def governance_snapshot(self) -> GovernanceSnapshot:
        for e in reversed(self.events):
            if e.stage == "govern":
                return self._dict_to_gs(e.payload)
        return GovernanceSnapshot()

    @staticmethod
    def _dict_to_gs(d: dict) -> GovernanceSnapshot:
        return GovernanceSnapshot(
            skill_count=d.get("skill_count", 0),
            quarantined_count=d.get("quarantined_count", 0),
            ecosystem_stability=d.get("ecosystem_stability", 1.0),
            churn_rate=d.get("churn_rate", 0.0),
            skill_statuses=d.get("skill_statuses", {}),
            global_policy_deny=d.get("global_policy_deny", []),
        )

    def get_trace_by_stage(self, stage: ExecutionStage) -> Any:
        """（已弃用）按阶段查事件。"""
        sv = stage.value if isinstance(stage, ExecutionStage) else stage
        for e in self.events:
            if e.stage == sv:
                return e
        return None

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（供 JSON 导出）。"""
        return {
            "trace_id": self.trace_id,
            "input": self.input,
            "timestamp": self.timestamp,
            "total_latency_s": self.total_latency_s,
            "overall_status": self.overall_status,
            "passed": self.passed,
            "risk_score": self.risk_score,
            "events": [
                {
                    "trace_id": e.trace_id,
                    "stage": e.stage,
                    "type": e.event_type,
                    "payload": _event_payload_summary(e.payload),
                    "timestamp": e.timestamp,
                }
                for e in self.events
            ],
        }


@dataclass
class DVXRuntimeModel:
    """DVXRuntimeModel v1.91 — 运行时统一模型（类型注册表）。"""
    pass


def _event_payload_summary(obj: Any) -> Any:
    """截断大 payload 为可读摘要。"""
    if isinstance(obj, dict):
        return {k: _event_payload_summary(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_event_payload_summary(v) for v in obj[:20]]
    s = str(obj)
    if len(s) > 300:
        return s[:300] + "..."
    return obj
