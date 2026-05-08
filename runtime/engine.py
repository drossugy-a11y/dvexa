"""DVXRuntimeEngine v1.91 — Event-Driven 运行时调度器

职责：
  - 只做调度：编排 stage 执行顺序
  - 传递 Event：每个 stage 的输出是 Event
  - 不做分析/决策/状态存储

依赖注入接收所有模块实例 + EventStore。
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from runtime.event import Event, EventStore
from runtime.models import (
    ExecutionStage,
    RuntimeContext,
    GovernanceSnapshot,
)

DVXLoader = Any
SemanticGovernanceLayer = Any
AssimilationTestSystem = Any
AssimilationScheduler = Any
SkillGovernor = Any


class DVXRuntimeEngine:
    """DVX Runtime Engine — Event-Driven 统一调度器。

    只做：
      - 编排 6 阶段执行
      - 将每个 stage 输出包装为 Event
      - Append 到 EventStore + RuntimeContext

    不做：
      - 分析/决策/状态存储
    """

    def __init__(
        self,
        dvx_loader: DVXLoader,
        sgl: SemanticGovernanceLayer,
        ats: AssimilationTestSystem,
        scheduler: AssimilationScheduler,
        governor: SkillGovernor | None = None,
        event_store: EventStore | None = None,
    ):
        self._dvx = dvx_loader
        self._sgl = sgl
        self._ats = ats
        self._scheduler = scheduler
        self._governor = governor
        self._event_store = event_store or EventStore()

    # ── Public API ────────────────────────────────────────────────────────

    def run(self, input_text: str) -> RuntimeContext:
        """执行完整流水线，每阶段输出 Event。

        Args:
            input_text: ACTION 格式输入文本。

        Returns:
            包含全量 Events 的 RuntimeContext。
        """
        ctx = RuntimeContext(
            input=input_text,
            trace_id=self._generate_trace_id(),
            timestamp=datetime.now().isoformat(),
            overall_status="running",
        )

        total_start = time.perf_counter()

        # ── Stage 1: LOAD ─────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            action = self._dvx.parse(input_text)
            event = Event(
                trace_id=ctx.trace_id,
                stage="load",
                event_type="info",
                payload={
                    "target": action.target,
                    "intent": action.intent,
                    "mode": action.mode,
                    "constraint": action.constraint,
                    "output": action.output,
                    "warnings": action.warnings,
                },
                metadata={"latency_s": time.perf_counter() - t0},
            )
            self._emit(ctx, event)
        except Exception as e:
            self._emit_error(ctx, "load", input_text, str(e), time.perf_counter() - t0)
            return self._finalize(ctx, total_start)

        # ── Stage 2: SEMANTIC ─────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            # 使用 Event transformer
            load_event = ctx.events[0]
            event = self._sgl.analyze_event(load_event)
            event.metadata["latency_s"] = time.perf_counter() - t0
            self._emit(ctx, event)
        except Exception as e:
            self._emit_error(ctx, "semantic", input_text, str(e), time.perf_counter() - t0)
            return self._finalize(ctx, total_start)

        # ── Stage 3: VALIDATE ─────────────────────────────────────────────
        t0 = time.perf_counter()
        dvx_payload = ctx.events[0].payload
        sgl_payload = ctx.events[1].payload
        target = dvx_payload.get("target", "")
        ats_context = {
            "intent": sgl_payload.get("intent", "unknown"),
            "mode": dvx_payload.get("mode", "observe"),
            "threat_type": sgl_payload.get("threat_type", "none"),
            "sgl_risk_score": sgl_payload.get("risk_score", 0.0),
            "governance_impact": sgl_payload.get("governance_impact", "advisory"),
        }
        if dvx_payload.get("constraint"):
            ats_context["constraint"] = dvx_payload["constraint"]

        try:
            # 使用 Event transformer
            ats_input_event = Event(
                trace_id=ctx.trace_id, stage="validate", event_type="info",
                payload={"target": target, "context": ats_context},
            )
            event = self._ats.run_event(ats_input_event)
            event.metadata["latency_s"] = time.perf_counter() - t0
            self._emit(ctx, event)
        except Exception as e:
            self._emit_error(ctx, "validate", {"target": target, "context": ats_context}, str(e), time.perf_counter() - t0)
            return self._finalize(ctx, total_start)

        # ── Stage 4: SCHEDULE ─────────────────────────────────────────────
        t0 = time.perf_counter()
        ats_payload = ctx.events[2].payload
        ats_risk = ats_payload.get("risk_score", 0.0)
        ats_passed = ats_payload.get("passed", False)

        try:
            # 使用 Event transformer
            scheduler_input = Event(
                trace_id=ctx.trace_id, stage="schedule", event_type="info",
                payload={
                    "target": target,
                    "risk_score": ats_risk,
                    "passed": ats_passed,
                    "capabilities": [],
                },
            )
            scheduler_events = self._scheduler.process_event(scheduler_input)
            for se in scheduler_events:
                se.metadata["latency_s"] = time.perf_counter() - t0
                self._emit(ctx, se)
        except Exception as e:
            error_event = Event(
                trace_id=ctx.trace_id, stage="schedule", event_type="error",
                payload={"error": str(e)},
                metadata={"latency_s": time.perf_counter() - t0},
            )
            self._emit(ctx, error_event)

        # ── Stage 5: GOVERN ───────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            gs = self._capture_governance_snapshot()
            event = Event(
                trace_id=ctx.trace_id,
                stage="govern",
                event_type="info",
                payload={
                    "skill_count": gs.skill_count,
                    "quarantined_count": gs.quarantined_count,
                    "ecosystem_stability": gs.ecosystem_stability,
                    "churn_rate": gs.churn_rate,
                    "skill_statuses": gs.skill_statuses,
                    "global_policy_deny": gs.global_policy_deny,
                },
                metadata={"latency_s": time.perf_counter() - t0},
            )
            self._emit(ctx, event)
        except Exception as e:
            self._emit_error(ctx, "govern", {}, str(e), time.perf_counter() - t0)

        # ── Stage 6: LOG ──────────────────────────────────────────────────
        t0 = time.perf_counter()
        log_entry = self._build_log_entry(ctx)
        event = Event(
            trace_id=ctx.trace_id,
            stage="log",
            event_type="info",
            payload=log_entry,
            metadata={"latency_s": time.perf_counter() - t0},
        )
        self._emit(ctx, event)

        return self._finalize(ctx, total_start)

    # ── Internal ──────────────────────────────────────────────────────────

    def _emit(self, ctx: RuntimeContext, event: Event) -> None:
        """Append event to EventStore + RuntimeContext。"""
        self._event_store.append(event)
        ctx.events.append(event)

    def _emit_error(
        self, ctx: RuntimeContext, stage: str, input_snapshot: Any, error: str, latency: float
    ) -> None:
        event = Event(
            trace_id=ctx.trace_id,
            stage=stage,
            event_type="error",
            payload={"error": error, "input": _snapshot_summary(input_snapshot)},
            metadata={"latency_s": latency},
        )
        self._emit(ctx, event)
        ctx.overall_status = "error"

    def _finalize(self, ctx: RuntimeContext, total_start: float) -> RuntimeContext:
        ctx.total_latency_s = time.perf_counter() - total_start
        if ctx.overall_status != "error":
            ctx.overall_status = "complete"
        return ctx

    def _generate_trace_id(self) -> str:
        return f"trc-{uuid.uuid4().hex[:12]}"

    def _capture_governance_snapshot(self) -> GovernanceSnapshot:
        if not self._governor:
            return GovernanceSnapshot()
        try:
            all_skills = self._governor.list_all() if hasattr(self._governor, "list_all") else []
            skill_statuses = {s["name"]: s.get("status", "unknown") for s in all_skills}
            global_policy = self._governor.get_policy("__global__") if hasattr(self._governor, "get_policy") else None
            return GovernanceSnapshot(
                skill_count=len(all_skills),
                quarantined_count=self._governor.quarantine_count() if hasattr(self._governor, "quarantine_count") else 0,
                ecosystem_stability=self._governor.ecosystem_stability_score() if hasattr(self._governor, "ecosystem_stability_score") else 1.0,
                churn_rate=self._governor.capability_churn_rate() if hasattr(self._governor, "capability_churn_rate") else 0.0,
                skill_statuses=skill_statuses,
                global_policy_deny=list(global_policy.deny) if global_policy else [],
            )
        except Exception:
            return GovernanceSnapshot()

    def _build_log_entry(self, ctx: RuntimeContext) -> dict:
        return {
            "trace_id": ctx.trace_id,
            "timestamp": ctx.timestamp,
            "input": ctx.input[:200],
            "passed": ctx.passed,
            "risk_score": ctx.risk_score,
            "stage_count": len(ctx.events),
            "stages": [e.stage for e in ctx.events],
        }

    @property
    def event_store(self) -> EventStore:
        return self._event_store

    @property
    def scheduler(self) -> Any:
        return self._scheduler


def _snapshot_summary(obj: Any) -> str:
    s = str(obj)
    if len(s) > 300:
        return s[:300] + "..."
    return s
