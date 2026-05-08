"""DVX Compiler v2.0 — 8 阶段编译流水线编排器

将 EventStore 事件流编译为 DXB (DVX Execution Blueprint)。
纯函数式流程，完全确定性，不做运行时决策。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from compiler_v2.capability_ir import (
    CapabilityIR,
    CapabilityNode,
    CapabilitySignal,
    DXB,
)

try:
    from compiler_v2.optimizer import DXBOptimizer, OptimizationReport
except ImportError:
    DXBOptimizer = None  # type: ignore[assignment]
    OptimizationReport = None  # type: ignore[assignment]

try:
    from compiler_v2.validator import DXBValidator, ValidationReport
except ImportError:
    DXBValidator = None  # type: ignore[assignment]
    ValidationReport = None  # type: ignore[assignment]


@dataclass
class CompilationDiagnostic:
    """编译诊断信息。"""
    stage: str
    level: str  # info | warning | error
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompilationResult:
    """编译结果 — Compiler 的唯一输出。"""
    dxb: DXB | None = None
    ir: CapabilityIR | None = None
    diagnostics: list[CompilationDiagnostic] = field(default_factory=list)
    optimization_report: Any = None  # OptimizationReport | None
    validation_report: Any = None  # ValidationReport | None
    compiled_at: float = 0.0

    @property
    def success(self) -> bool:
        if self.dxb is None:
            return False
        if self.validation_report is not None and not self.validation_report.valid:
            return False
        return not any(d.level == "error" for d in self.diagnostics)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "warning")


def _extract_payload_risk(payload: dict) -> float | None:
    """从 payload 中提取风险值，支持多个 key 名。

    搜索顺序: risk_score, risk_level, risk, threat_score
    返回找到的最大风险值（防止攻击者同时提供低 risk_score 和高 risk_level）。
    返回 None 表示无风险。
    """
    max_risk: float | None = None
    for key in ("risk_score", "risk_level", "risk", "threat_score"):
        value = payload.get(key)
        if isinstance(value, (int, float)) and value > 0:
            risk_val = float(value)
            if max_risk is None or risk_val > max_risk:
                max_risk = risk_val
    return max_risk


class DVXCompiler:
    """DVX v2.0 编译器 — 8 阶段编译流水线。

    将事件流编译为确定性的 DXB 执行蓝图。
    纯函数式转换，无副作用，无运行时决策。

    流水线:
      1. ingest_eventstore   — 加载事件
      2. extract_capabilities — 提取能力信号
      3. merge_capability_space — 合并能力空间
      4. build_capability_ir  — 构建 IR
      5. build_dxb            — 构建 DXB
      6. optimize_dxb         — 结构优化
      7. validate_dxb         — 安全验证
      8. emit_final_dxb       — 发射最终 DXB
    """

    def __init__(self) -> None:
        from compiler_v2.dxb_builder import DXBBuilder
        self._builder = DXBBuilder()
        self._optimizer = DXBOptimizer() if DXBOptimizer else None
        self._validator = DXBValidator() if DXBValidator else None

    def compile(
        self,
        events: list | None = None,
        trace_id: str = "",
        memory_outputs: list[dict] | None = None,
    ) -> CompilationResult:
        """执行完整 8 阶段编译流水线。

        Args:
            events: EventStore 事件列表
            trace_id: 追踪 ID
            memory_outputs: OpenClaw memory 输出（可选）

        Returns:
            CompilationResult 包含 DXB + 诊断 + 报告
        """
        diagnostics: list[CompilationDiagnostic] = []
        events = events or []

        # Stage 1: Ingest events
        loaded_events = self._stage_ingest(events, trace_id, diagnostics)
        if not loaded_events:
            return CompilationResult(diagnostics=diagnostics)

        # Stage 2: Extract capabilities
        signals = self._stage_extract(loaded_events, memory_outputs, diagnostics)

        # Stage 3: Merge capability space
        merged_signals = self._stage_merge(signals, diagnostics)

        # Stage 3.5: Normalize schema (对抗性加固)
        normalized_signals = self._stage_normalize_schema(merged_signals, diagnostics)

        # Stage 4: Build CapabilityIR
        ir = self._stage_build_ir(loaded_events, normalized_signals, trace_id, diagnostics)

        # Stage 5: Build DXB
        dxb = self._stage_build_dxb(ir, loaded_events, memory_outputs, diagnostics)
        if dxb is None:
            return CompilationResult(ir=ir, diagnostics=diagnostics)

        # Stage 6: Optimize
        opt_report = self._stage_optimize(dxb, diagnostics)

        # Stage 7: Validate (pass IR for integrity checks)
        val_report = self._stage_validate(dxb, ir, diagnostics)

        # Stage 8: Emit
        return self._stage_emit(dxb, ir, diagnostics, opt_report, val_report)

    # ── Stage 1: Ingest ──────────────────────────────────────────

    def _stage_ingest(
        self,
        events: list,
        trace_id: str,
        diagnostics: list[CompilationDiagnostic],
    ) -> list:
        """Stage 1: 加载并过滤事件。"""
        if trace_id:
            filtered = [e for e in events if getattr(e, 'trace_id', '') == trace_id]
        else:
            filtered = list(events)

        if not filtered:
            diagnostics.append(CompilationDiagnostic(
                stage="ingest",
                level="warning",
                message="No events loaded for compilation",
            ))
        else:
            diagnostics.append(CompilationDiagnostic(
                stage="ingest",
                level="info",
                message=f"Loaded {len(filtered)} events",
                detail={"event_count": len(filtered), "trace_id": trace_id},
            ))

        return filtered

    # ── Stage 2: Extract Capabilities ─────────────────────────────

    def _stage_extract(
        self,
        events: list,
        memory_outputs: list[dict] | None,
        diagnostics: list[CompilationDiagnostic],
    ) -> list[CapabilitySignal]:
        """Stage 2: 从事件中提取能力信号。

        提取规则:
        - 每个事件的 stage 映射为 capability 类型
        - 从 payload 中提取可用字段
        - 整合 OpenClaw memory 信号
        """
        signals: list[CapabilitySignal] = []

        for evt in events:
            stage = getattr(evt, 'stage', '')
            payload = getattr(evt, 'payload', {})
            tid = getattr(evt, 'trace_id', '')

            if stage == "load":
                signals.append(CapabilitySignal(
                    source="eventstore",
                    signal_type="context_load",
                    payload={"context": payload.get("context", ""), "input": payload.get("input", "")},
                    trace_id=tid,
                ))
            elif stage == "semantic":
                intent = payload.get("intent", "")
                if intent:
                    signals.append(CapabilitySignal(
                        source="eventstore",
                        signal_type="semantic_intent",
                        payload={"intent": intent, "risk_score": payload.get("risk_score", 0.0)},
                        confidence=0.8,
                        trace_id=tid,
                    ))
                threat = payload.get("threat_type", "")
                if threat and threat != "none":
                    signals.append(CapabilitySignal(
                        source="eventstore",
                        signal_type="threat_detected",
                        payload={"threat_type": threat},
                        confidence=0.9,
                        trace_id=tid,
                    ))
            elif stage == "validate":
                phases = payload.get("phases", [])
                if phases:
                    signals.append(CapabilitySignal(
                        source="eventstore",
                        signal_type="validation_phases",
                        payload={"phases": phases, "passed": payload.get("passed", True)},
                        confidence=0.85,
                        trace_id=tid,
                    ))
            elif stage == "schedule":
                action = payload.get("action", "")
                if action:
                    signals.append(CapabilitySignal(
                        source="eventstore",
                        signal_type="scheduled_action",
                        payload={"action": action, "result": payload.get("result", "")},
                        confidence=0.9,
                        trace_id=tid,
                    ))

        from compiler_v2.openclaw_adapter import OpenClawMemoryAdapter
        adapter = OpenClawMemoryAdapter()
        memory_signals: list[CapabilitySignal] = []
        try:
            safe_memory = memory_outputs if isinstance(memory_outputs, list) else []
            memory_signals = adapter.extract_capabilities(safe_memory)
        except Exception as exc:
            diagnostics.append(CompilationDiagnostic(
                stage="extract",
                level="error",
                message=f"Memory capability extraction failed: {exc}",
                detail={"memory_outputs_type": type(memory_outputs).__name__ if memory_outputs is not None else "None"},
            ))
        signals.extend(memory_signals)

        diagnostics.append(CompilationDiagnostic(
            stage="extract",
            level="info",
            message=f"Extracted {len(signals)} capability signals",
            detail={"total": len(signals), "memory_signals": len(memory_signals)},
        ))

        return signals

    # ── Stage 3: Merge Capability Space ───────────────────────────

    def _stage_merge(
        self,
        signals: list[CapabilitySignal],
        diagnostics: list[CompilationDiagnostic],
    ) -> list[CapabilitySignal]:
        """Stage 3: 合并去重能力信号。

        合并规则:
        - 相同 signal_type + trace_id 只保留最高 confidence
        - 不同 trace_id 的信号保留
        """
        merged: dict[tuple[str, str], CapabilitySignal] = {}

        for sig in signals:
            key = (sig.signal_type, sig.trace_id)
            if key in merged:
                if sig.confidence > merged[key].confidence:
                    merged[key] = sig
            else:
                merged[key] = sig

        result = list(merged.values())
        removed = len(signals) - len(result)

        diagnostics.append(CompilationDiagnostic(
            stage="merge",
            level="info",
            message=f"Merged signals: {len(signals)} → {len(result)} ({removed} deduped)",
            detail={"before": len(signals), "after": len(result), "removed": removed},
        ))

        return result

    # ── Stage 3.5: Normalize Schema ───────────────────────────────

    def _stage_normalize_schema(
        self,
        signals: list[CapabilitySignal],
        diagnostics: list[CompilationDiagnostic],
    ) -> list[CapabilitySignal]:
        """Stage 3.5: Schema 归一化 — 映射不同 payload key 到编译器标准 key。

        规范化映射（支持别名到标准字段）:
          risk_level → risk_score
          checks → phases
          trigger → result
          quarantine_reason → reason（双向支持）
        """
        FIELD_ALIASES = {
            "risk_level": "risk_score",
            "checks": "phases",
            "trigger": "result",
        }

        # 风险字段集合 — 同时存在时取最大值而非覆盖
        RISK_FIELDS = {"risk_score", "risk_level", "risk", "threat_score"}

        normalized_signals: list[CapabilitySignal] = []
        normalization_count = 0

        for sig in signals:
            payload = dict(sig.payload)
            changed = False
            for alias, standard in FIELD_ALIASES.items():
                if alias in payload:
                    if standard in payload and standard in RISK_FIELDS:
                        # 风险字段同时存在 — 取更保守的值（最高风险）
                        try:
                            alias_val = float(payload[alias])
                            standard_val = float(payload[standard])
                            merged = max(alias_val, standard_val)
                            if merged != standard_val:
                                payload[standard] = merged
                                changed = True
                                normalization_count += 1
                        except (ValueError, TypeError):
                            pass
                    elif standard not in payload:
                        payload[standard] = payload[alias]
                        changed = True
                        normalization_count += 1

            if changed:
                normalized_signals.append(CapabilitySignal(
                    source=sig.source,
                    signal_type=sig.signal_type,
                    payload=payload,
                    confidence=sig.confidence,
                    trace_id=sig.trace_id,
                ))
            else:
                normalized_signals.append(sig)

        if normalization_count > 0:
            diagnostics.append(CompilationDiagnostic(
                stage="normalize_schema",
                level="info",
                message=f"Normalized {normalization_count} payload fields",
                detail={"normalized_count": normalization_count},
            ))

        return normalized_signals

    # ── Stage 4: Build CapabilityIR ───────────────────────────────

    def _stage_build_ir(
        self,
        events: list,
        signals: list[CapabilitySignal],
        trace_id: str,
        diagnostics: list[CompilationDiagnostic],
    ) -> CapabilityIR:
        """Stage 4: 构建 CapabilityIR。

        从 signals 中提取:
        - intent (从 semantic_intent signal)
        - capabilities (所有 signal 映射为 CapabilityNode)
        - risk_signals (从 threat_detected 等 signal)
        - governance_constraints (从 policy signals)
        """
        ir = CapabilityIR(trace_id=trace_id)

        for sig in signals:
            if sig.signal_type == "semantic_intent":
                ir.intent = sig.payload.get("intent", "")
                ir.target = sig.payload.get("target", "")

            if sig.signal_type == "threat_detected":
                ir.risk_signals[sig.payload.get("threat_type", "unknown")] = sig.confidence
            elif "risk" in sig.signal_type.lower():
                ir.risk_signals[sig.signal_type] = sig.confidence

            # 增强风险提取: 从 payload 中扫描风险字段
            payload_risk = _extract_payload_risk(sig.payload)
            if payload_risk is not None:
                source_key = f"payload:{sig.signal_type}"
                ir.risk_signals[source_key] = payload_risk
                diagnostics.append(CompilationDiagnostic(
                    stage="build_ir",
                    level="info",
                    message=f"Extracted risk={payload_risk} from payload of signal '{sig.signal_type}'",
                    detail={"signal_type": sig.signal_type, "payload_risk": payload_risk},
                ))

            node_type = self._signal_to_node_type(sig.signal_type)
            node_id = f"{sig.signal_type}:{sig.trace_id}" if sig.trace_id else f"{sig.signal_type}:{id(sig)}"
            ir.capabilities.append(CapabilityNode(
                id=node_id,
                node_type=node_type,
                name=sig.signal_type,
                metadata={"payload": sig.payload, "confidence": sig.confidence},
            ))

        # 风险覆盖完整性检查 — 确保所有 payload 风险被提取
        signals_with_risk = 0
        signals_with_risk_extracted = 0
        for sig in signals:
            pr = _extract_payload_risk(sig.payload)
            if pr is not None:
                signals_with_risk += 1
                if f"payload:{sig.signal_type}" in ir.risk_signals:
                    signals_with_risk_extracted += 1
        if signals_with_risk > 0 and signals_with_risk_extracted < signals_with_risk:
            diagnostics.append(CompilationDiagnostic(
                stage="build_ir",
                level="warning",
                message=f"RISK EXTRACTION GAP: {signals_with_risk - signals_with_risk_extracted}/{signals_with_risk} "
                        "signals with payload risk were not captured in risk_signals",
            ))

        if ir.intent:
            ir.extracted_patterns = [ir.intent]

        diagnostics.append(CompilationDiagnostic(
            stage="build_ir",
            level="info",
            message=f"Built CapabilityIR with {ir.capability_count()} nodes",
            detail={"intent": ir.intent, "nodes": ir.capability_count(), "patterns": ir.extracted_patterns},
        ))

        return ir

    @staticmethod
    def _signal_to_node_type(signal_type: str) -> str:
        """将 signal_type 映射到 node_type。"""
        mapping = {
            "context_load": "RUNTIME_ACTION",
            "semantic_intent": "SKILL",
            "threat_detected": "GOVERNANCE_CHECK",
            "validation_phases": "GOVERNANCE_CHECK",
            "scheduled_action": "RUNTIME_ACTION",
            "memory_capability": "MEMORY",
        }
        return mapping.get(signal_type, "SKILL")

    # ── Stage 5: Build DXB ────────────────────────────────────────

    def _stage_build_dxb(
        self,
        ir: CapabilityIR,
        events: list,
        memory_outputs: list[dict] | None,
        diagnostics: list[CompilationDiagnostic],
    ) -> DXB | None:
        """Stage 5: 从 IR 构建 DXB。"""
        try:
            dxb = self._builder.build(ir, events, memory_outputs, diagnostics)
            diagnostics.append(CompilationDiagnostic(
                stage="build_dxb",
                level="info",
                message=f"Built DXB with {dxb.step_count} steps",
                detail={"steps": dxb.step_count, "dag_size": len(dxb.dag)},
            ))
            return dxb
        except Exception as exc:
            diagnostics.append(CompilationDiagnostic(
                stage="build_dxb",
                level="error",
                message=f"DXB build failed: {exc}",
            ))
            return None

    # ── Stage 6: Optimize ─────────────────────────────────────────

    def _stage_optimize(
        self,
        dxb: DXB,
        diagnostics: list[CompilationDiagnostic],
    ) -> Any:  # OptimizationReport | None
        """Stage 6: 结构优化 DXB。"""
        if self._optimizer is None:
            diagnostics.append(CompilationDiagnostic(
                stage="optimize",
                level="warning",
                message="Optimizer not available, skipping",
            ))
            return None

        try:
            report = self._optimizer.optimize(dxb)
            diagnostics.append(CompilationDiagnostic(
                stage="optimize",
                level="info",
                message=f"Optimized: {report.original_step_count} → {report.optimized_step_count} steps",
            ))
            return report
        except Exception as exc:
            diagnostics.append(CompilationDiagnostic(
                stage="optimize",
                level="warning",
                message=f"Optimization skipped: {exc}",
            ))
            return None

    # ── Stage 7: Validate ─────────────────────────────────────────

    def _stage_validate(
        self,
        dxb: DXB,
        ir: CapabilityIR | None,
        diagnostics: list[CompilationDiagnostic],
    ) -> Any:  # ValidationReport | None
        """Stage 7: 验证 DXB 安全性。

        Args:
            dxb: 待验证的 DXB
            ir: 可选的 CapabilityIR，用于完整性检查
            diagnostics: 诊断列表
        """
        if self._validator is None:
            diagnostics.append(CompilationDiagnostic(
                stage="validate",
                level="warning",
                message="Validator not available, skipping",
            ))
            return None

        try:
            report = self._validator.validate(dxb, ir)
            level = "info" if report.valid else "error"
            diagnostics.append(CompilationDiagnostic(
                stage="validate",
                level=level,
                message=f"Validation: {'PASSED' if report.valid else 'FAILED'}",
                detail={"errors": report.errors, "warnings": report.warnings},
            ))
            return report
        except Exception as exc:
            diagnostics.append(CompilationDiagnostic(
                stage="validate",
                level="error",
                message=f"Validation error: {exc}",
            ))
            return None

    # ── Stage 8: Emit ─────────────────────────────────────────────

    def _stage_emit(
        self,
        dxb: DXB,
        ir: CapabilityIR,
        diagnostics: list[CompilationDiagnostic],
        opt_report: Any,  # OptimizationReport | None
        val_report: Any,  # ValidationReport | None
    ) -> CompilationResult:
        """Stage 8: 发射最终编译结果。"""
        result = CompilationResult(
            dxb=dxb,
            ir=ir,
            diagnostics=diagnostics,
            optimization_report=opt_report,
            validation_report=val_report,
            compiled_at=time.time(),
        )

        if result.success:
            diagnostics.append(CompilationDiagnostic(
                stage="emit",
                level="info",
                message="Compilation successful",
                detail={"dxb_id": dxb.id, "steps": dxb.step_count},
            ))
        else:
            diagnostics.append(CompilationDiagnostic(
                stage="emit",
                level="error",
                message="Compilation failed — see diagnostics",
            ))

        return result
