"""SystemSnapshotBuilder — 一次性聚合所有子系统状态。

无副作用、只读、deterministic。
从 10+ 个现有模块收集数据，不修改任何状态。
"""

from __future__ import annotations

import time
from typing import Any

from surface.dto import SystemSnapshot


class SystemSnapshotBuilder:
    """系统快照构建器。

    接收所有 system dependency 的可选引用，build() 时聚合状态。
    任何依赖缺失时静默跳过对应数据——不崩溃。
    """

    def __init__(
        self,
        capability_registry: Any = None,
        evolution_tracker: Any = None,
        meta_control_plane: Any = None,
        memory: Any = None,
        insight_agent: Any = None,
        governor: Any = None,
        cost_model: Any = None,
        pattern_registry: Any = None,
        external_reporter: Any = None,
    ):
        self._capability_registry = capability_registry
        self._evolution_tracker = evolution_tracker
        self._meta_control_plane = meta_control_plane
        self._memory = memory
        self._insight_agent = insight_agent
        self._governor = governor
        self._cost_model = cost_model
        self._pattern_registry = pattern_registry
        self._external_reporter = external_reporter

    def build(self) -> SystemSnapshot:
        """构建当前系统快照。"""
        return SystemSnapshot(
            timestamp=self._now(),
            task_count=self._get_task_count(),
            system_health=self._get_health(),
            capability_summary=self._get_capability_summary(),
            evolution_report=self._get_evolution_report(),
            governance_status=self._get_governance_status(),
            execution_history=self._get_execution_history(),
            insight_report=self._get_insight_report(),
            metric_summary=self._get_metric_summary(),
        )

    # ── 内部收集方法 ──────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    def _get_task_count(self) -> int:
        if self._memory:
            try:
                return len(self._memory.get_all())
            except Exception:
                pass
        return 0

    def _get_health(self) -> str:
        if self._insight_agent:
            try:
                return self._insight_agent.quick_health()
            except Exception:
                pass
        return "unknown"

    def _get_capability_summary(self) -> dict:
        summary: dict = {}
        if self._capability_registry:
            try:
                summary["registry"] = self._capability_registry.get_summary()
                summary["node_count"] = self._capability_registry.count
                summary["high_risk"] = [
                    n.capability_id
                    for n in self._capability_registry.get_high_risk_capabilities()
                ]
            except Exception:
                pass
        if self._pattern_registry:
            try:
                summary["patterns"] = self._pattern_registry.get_summary()
            except Exception:
                pass
        return summary

    def _get_evolution_report(self) -> dict:
        if self._evolution_tracker:
            try:
                return self._evolution_tracker.generate_evolution_report()
            except Exception:
                pass
        return {}

    def _get_governance_status(self) -> dict:
        status: dict = {}
        if self._meta_control_plane:
            try:
                mcp = self._meta_control_plane
                health = mcp.get_health_monitor().assess({})
                perm = mcp.get_permission_engine().evaluate(health, {})
                gate = mcp.get_gate().check(health, perm)
                status["health_score"] = health.get("health_score", 0)
                status["health_status"] = health.get("status", "unknown")
                status["signals"] = health.get("signals", [])
                status["permission_mode"] = perm.get("mode", "FROZEN")
                status["can_optimize"] = gate.get("can_optimize", False)
                status["process_count"] = mcp.get_process_count()
                status["snapshot_count"] = mcp.get_snapshot_manager().get_snapshot_count()
            except Exception:
                pass
        if self._governor:
            try:
                status["skill_count"] = len(self._governor._scores)
                status["quarantined"] = [
                    s for s, st in self._governor._statuses.items()
                    if hasattr(st, "value") and st.value == "QUARANTINED"
                ]
            except Exception:
                pass
        return status

    def _get_execution_history(self) -> list[dict]:
        if self._memory:
            try:
                return self._memory.get_all()[-50:]  # 最近 50 条
            except Exception:
                pass
        return []

    def _get_insight_report(self) -> dict:
        if self._insight_agent:
            try:
                return self._insight_agent.generate_report()
            except Exception:
                pass
        return {}

    def _get_metric_summary(self) -> dict:
        metrics: dict = {}
        if self._cost_model:
            try:
                metrics["cost_table"] = dict(self._cost_model.cost_table)
            except Exception:
                pass
        if self._external_reporter:
            try:
                metrics["external_calls"] = self._external_reporter.summary()
            except Exception:
                pass
        return metrics
