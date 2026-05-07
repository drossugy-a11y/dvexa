"""DXB Builder v2.0 — CapabilityIR → DXB 执行蓝图构建器

纯结构编译，将 IR 转换为可执行 DXB，不做运行时决策。
"""

from __future__ import annotations

import uuid
from typing import Any

from compiler_v2.capability_ir import (
    CapabilityIR,
    CapabilityNode,
    CapabilitySignal,
    CapabilityStep,
    DXB,
)
from compiler_v2.openclaw_adapter import OpenClawMemoryAdapter
from compiler_v2.policy_injector import PolicyInjector


class DXBBuilder:
    """DXB 构建器 — 将 CapabilityIR 编译为 DXB 执行蓝图。

    纯结构编译器，不做任何运行时决策。
    输入: CapabilityIR + Events + Memory Outputs
    输出: DXB (包含 steps, dag, constraints)
    """

    def __init__(self) -> None:
        self._policy = PolicyInjector()
        self._adapter = OpenClawMemoryAdapter()

    def build(
        self,
        ir: CapabilityIR,
        events: list | None = None,
        memory_outputs: list[dict] | None = None,
    ) -> DXB:
        """从 CapabilityIR 构建完整的 DXB。

        Args:
            ir: 能力中间表示
            events: 原始事件列表（用于提取治理约束）
            memory_outputs: 外部 memory 输出（OpenClaw #003）

        Returns:
            完整的 DXB 对象
        """
        dxb_id = f"dxb:{ir.trace_id or uuid.uuid4().hex[:8]}"

        steps = self._build_steps(ir)

        constraints = self._build_constraints(ir, events or [])

        memory_signals = self._adapter.extract_capabilities(memory_outputs)
        if memory_signals:
            self._annotate_steps_with_signals(steps, memory_signals)

        return DXB(
            id=dxb_id,
            steps=steps,
            constraints=constraints,
            origin_trace_id=ir.trace_id,
        )

    def _build_steps(self, ir: CapabilityIR) -> list[CapabilityStep]:
        """将 IR 中的 CapabilityNode 转换为 CapabilityStep 列表。

        排序规则:
        - GOVERNANCE_CHECK 节点始终排在前面
        - SKILL 节点排在中间，依赖 governance steps
        - TOOL 节点排在最后，依赖 skill steps
        - 每个步骤的风险从 ir.risk_signals 中获取
        """
        steps: list[CapabilityStep] = []
        governance_deps: list[str] = []
        skill_deps: list[str] = []

        # Phase 1: Governance checks first
        for node in ir.capabilities:
            if node.node_type == "GOVERNANCE_CHECK":
                sid = f"step:{node.id}"
                risk = ir.risk_signals.get(node.name, 0.0)
                steps.append(CapabilityStep(
                    id=sid,
                    step_type="GOVERNANCE_CHECK",
                    capability_ref=node.name,
                    risk=risk,
                    preconditions=list(node.metadata.get("preconditions", [])),
                    postconditions=list(node.metadata.get("postconditions", [])),
                ))
                governance_deps.append(sid)

        # Phase 2: Skills
        for node in ir.capabilities:
            if node.node_type == "SKILL":
                sid = f"step:{node.id}"
                risk = ir.risk_signals.get(node.name, 0.0)
                steps.append(CapabilityStep(
                    id=sid,
                    step_type="SKILL",
                    capability_ref=node.name,
                    dependencies=list(governance_deps),
                    risk=risk,
                    inputs=dict(node.metadata.get("inputs", {})),
                    expected_output=dict(node.metadata.get("expected_output", {})),
                ))
                skill_deps.append(sid)

        # Phase 3: Tools
        for node in ir.capabilities:
            if node.node_type == "TOOL":
                sid = f"step:{node.id}"
                risk = ir.risk_signals.get(node.name, 0.0)
                steps.append(CapabilityStep(
                    id=sid,
                    step_type="TOOL",
                    capability_ref=node.name,
                    dependencies=list(skill_deps),
                    risk=risk,
                    inputs=dict(node.metadata.get("inputs", {})),
                    expected_output=dict(node.metadata.get("expected_output", {})),
                ))

        return steps

    def _build_constraints(
        self, ir: CapabilityIR, events: list
    ) -> dict[str, Any]:
        """合并 IR 治理约束 + PolicyInjector 约束。"""
        constraints: dict[str, Any] = dict(ir.governance_constraints)
        policy_constraints = self._policy.inject_all(events)
        constraints["policy"] = policy_constraints
        constraints["compiled_from"] = "CapabilityIR"
        return constraints

    def _annotate_steps_with_signals(
        self, steps: list[CapabilityStep], signals: list[CapabilitySignal]
    ) -> None:
        """将 OpenClaw memory 信号信息附加到相关步骤的 inputs 中。

        由于 CapabilityStep 是 frozen dataclass，需要创建新实例替换。
        """
        signal_map: dict[str, list[dict[str, Any]]] = {}
        for sig in signals:
            cap = sig.payload.get("capability", "")
            if cap:
                signal_map.setdefault(cap, []).append({
                    "source": sig.source,
                    "confidence": sig.confidence,
                    "payload": sig.payload,
                })

        for i, step in enumerate(steps):
            merged_signals: list[dict[str, Any]] = []
            for cap_name, sig_data in signal_map.items():
                ref_lower = step.capability_ref.lower()
                cap_lower = cap_name.lower()
                cap_compact = cap_name.replace("_", "").lower()
                if cap_lower in ref_lower or cap_compact in ref_lower:
                    merged_signals.extend(sig_data)

            if merged_signals:
                current_inputs = dict(step.inputs)
                existing = current_inputs.get("external_signals", [])
                if isinstance(existing, list):
                    current_inputs["external_signals"] = existing + merged_signals
                else:
                    current_inputs["external_signals"] = merged_signals

                steps[i] = CapabilityStep(
                    id=step.id,
                    step_type=step.step_type,
                    capability_ref=step.capability_ref,
                    inputs=current_inputs,
                    dependencies=list(step.dependencies),
                    risk=step.risk,
                    preconditions=list(step.preconditions),
                    postconditions=list(step.postconditions),
                    expected_output=dict(step.expected_output),
                )
