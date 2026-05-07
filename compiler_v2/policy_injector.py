"""Policy Injector v2.0 — 治理策略注入器

将 SGL/ATS/Scheduler 的事件输出转换为编译时约束，
注入 DXB，不参与运行时决策。
"""

from __future__ import annotations

from typing import Any

from runtime.event import Event


class PolicyInjector:
    """治理策略注入器。

    从 governance events (SGL/ATS/Scheduler) 中提取约束，
    转换为 DXB constraints，在编译时完成所有治理决策。

    注意：
      - 只提取约束规则，不做决策
      - 不调用 SGL.analyze() / ATS.run() 等旧 API
      - 输入是已完成的事件，输出是约束字典
    """

    def inject_sgl_constraints(self, semantic_events: list[Event]) -> dict[str, Any]:
        """从 SGL semantic 事件中提取约束。

        Returns:
            {"intent_constraint": str, "risk_threshold": float, "threat_type": str}
        """
        constraints: dict[str, Any] = {}
        risk_scores: list[float] = []

        for evt in semantic_events:
            if evt.stage != "semantic":
                continue
            payload = evt.payload

            # 意图约束
            intent = payload.get("intent", "")
            if intent:
                constraints["intent_constraint"] = intent

            # 风险阈值
            risk = payload.get("risk_score", 0.0)
            if isinstance(risk, (int, float)) and risk > 0:
                risk_scores.append(risk)

            # 威胁类型
            threat = payload.get("threat_type", "")
            if threat and threat != "none":
                constraints["threat_type"] = threat

            # 治理影响
            gov_impact = payload.get("governance_impact", "")
            if gov_impact:
                constraints["governance_impact"] = gov_impact

        if risk_scores:
            constraints["risk_threshold"] = max(risk_scores)
        else:
            constraints["risk_threshold"] = 0.0

        return constraints

    def inject_ats_constraints(self, validate_events: list[Event]) -> dict[str, Any]:
        """从 ATS validation 事件中提取约束。

        Returns:
            {"passed": bool, "phases": list, "risk_score": float}
        """
        constraints: dict[str, Any] = {"passed": True}
        risk_scores: list[float] = []
        all_phases: list[str] = []

        for evt in validate_events:
            if evt.stage != "validate":
                continue
            payload = evt.payload

            passed = payload.get("passed", True)
            if not passed:
                constraints["passed"] = False
                constraints["failure_reason"] = payload.get("reason", "validation failed")

            risk = payload.get("risk_score", 0.0)
            if isinstance(risk, (int, float)):
                risk_scores.append(risk)

            phases = payload.get("phases", [])
            if isinstance(phases, list):
                all_phases.extend(phases)

        if risk_scores:
            constraints["risk_score"] = max(risk_scores)
        if all_phases:
            constraints["phases"] = list(dict.fromkeys(all_phases))

        return constraints

    def inject_scheduler_constraints(self, schedule_events: list[Event]) -> dict[str, Any]:
        """从 Scheduler 事件中提取调度约束。

        Returns:
            {"final_state": str, "action": str, "quarantine_reason": str}
        """
        constraints: dict[str, Any] = {}

        for evt in schedule_events:
            if evt.stage != "schedule":
                continue
            payload = evt.payload

            action = payload.get("action", "")
            if action:
                constraints["action"] = action

            result = payload.get("result", "")
            if result:
                constraints["final_state"] = result

            reason = payload.get("reason", "") or payload.get("quarantine_reason", "")
            if reason:
                constraints["quarantine_reason"] = reason

        return constraints

    def inject_all(self, events: list[Event]) -> dict[str, Any]:
        """从所有事件中提取并合并治理约束。

        Args:
            events: 完整的 trace 事件列表

        Returns:
            合并后的约束字典，包含 sgl / ats / scheduler 三个子域
        """
        semantic_events = [e for e in events if e.stage == "semantic"]
        validate_events = [e for e in events if e.stage == "validate"]
        schedule_events = [e for e in events if e.stage == "schedule"]

        return {
            "sgl": self.inject_sgl_constraints(semantic_events),
            "ats": self.inject_ats_constraints(validate_events),
            "scheduler": self.inject_scheduler_constraints(schedule_events),
            "compiled_at": "compile-time",
            "runtime_decision": False,
        }
