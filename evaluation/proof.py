"""Layer 1: ExecutionProof — captures and formats complete execution proof.

Dual-format output (JSON + human-readable text).
Sources real data from: kernel execution, EventStore trace, governance modules.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class StrategyRecord:
    """A single execution strategy with planning, scoring, and result."""
    id: int
    description: str
    plan: dict
    ats_score: dict | None = None
    selected: bool = False
    selection_reason: str = ""


@dataclass
class ToolCallRecord:
    """A single tool invocation during execution."""
    step_id: int
    action: str
    tool: str
    tool_input: str
    tool_output_summary: str
    latency_s: float = 0.0
    success: bool = True


@dataclass
class ExecutionProof:
    """Layer 1 — captures and formats complete execution proof.

    Populated from a real kernel run, then serialized to JSON or text.
    """
    # Task context
    task_input: str = ""
    task_id: str = ""
    goal: str = ""

    # Planning phase
    strategies: list[StrategyRecord] = field(default_factory=list)

    # Execution phase
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    total_tokens: int = 0
    total_latency_s: float = 0.0
    estimated_cost_usd: float = 0.0

    # Result
    success: bool = False
    result_summary: str = ""
    error: str = ""

    # Governance context
    governance_events: list[dict] = field(default_factory=list)
    risk_signals: list[dict] = field(default_factory=list)

    # Runtime metadata
    compiled_at: float = 0.0

    def __post_init__(self):
        if not self.compiled_at:
            self.compiled_at = time.time()

    # ── Builders ──────────────────────────────────────────────────────────

    @classmethod
    def from_kernel_result(
        cls,
        task_input: str,
        kernel_result: dict,
        strategies: list[StrategyRecord] | None = None,
        governance_events: list | None = None,
    ) -> ExecutionProof:
        """Build proof from a DVexaKernel.run_task() result."""
        steps = kernel_result.get("steps", [])
        plan = kernel_result.get("plan", [])

        tool_calls = []
        for s in steps:
            record = s if isinstance(s, dict) else {}
            tc = ToolCallRecord(
                step_id=record.get("step_id", 0),
                action=record.get("action", ""),
                tool=record.get("tool", ""),
                tool_input=str(record.get("tool_input", ""))[:200],
                tool_output_summary=str(record.get("tool_output", ""))[:200],
                success="error" not in str(record.get("tool_output", "")).lower(),
            )
            tool_calls.append(tc)

        return cls(
            task_input=task_input,
            task_id=kernel_result.get("task_id", ""),
            goal=kernel_result.get("goal", ""),
            strategies=strategies or [],
            tool_calls=tool_calls,
            total_tokens=sum(
                s.get("tokens", 0) if isinstance(s, dict) else 0
                for s in steps
            ),
            total_latency_s=0.0,
            success=kernel_result.get("status") == "completed",
            result_summary=str(kernel_result.get("result", ""))[:500],
            error=kernel_result.get("error", ""),
            governance_events=[
                {"stage": getattr(e, "stage", ""), "type": getattr(e, "event_type", ""), "payload": getattr(e, "payload", {})}
                for e in (governance_events or [])
            ],
        )

    def add_strategy(self, strategy: StrategyRecord) -> None:
        self.strategies.append(strategy)

    def add_tool_call(self, call: ToolCallRecord) -> None:
        self.tool_calls.append(call)

    # ── Serialization ────────────────────────────────────────────────────

    def to_json(self, indent: int = 2) -> str:
        """Machine-readable JSON output."""
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False, default=str)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        """Human-readable execution proof."""
        lines = [
            "=" * 60,
            "  DVexa Execution Proof",
            "=" * 60,
            "",
            f"  Task:          {self.task_input[:120]}",
            f"  Task ID:       {self.task_id}",
            f"  Goal:          {self.goal[:120]}",
            f"  Success:       {'✓' if self.success else '✗'}",
            f"  Latency:       {self.total_latency_s:.2f}s",
            f"  Estimated Cost: ${self.estimated_cost_usd:.6f}",
            "",
        ]

        # Strategies
        lines.extend([
            "─" * 40,
            "  STRATEGIES EVALUATED",
            "─" * 40,
        ])
        for s in self.strategies:
            marker = "▶ SELECTED" if s.selected else "  "
            lines.append(f"  {marker} Strategy #{s.id}: {s.description}")
            if s.ats_score:
                lines.append(f"       ATS score: {s.ats_score}")
            if s.selected and s.selection_reason:
                lines.append(f"       Reason: {s.selection_reason}")
        lines.append("")

        # Tool calls
        lines.extend([
            "─" * 40,
            "  TOOL EXECUTION TRACE",
            "─" * 40,
        ])
        for tc in self.tool_calls:
            status = "✓" if tc.success else "✗"
            lines.append(f"  Step {tc.step_id} [{status}] {tc.tool}")
            lines.append(f"       Action: {tc.action[:80]}")
            lines.append(f"       Input:  {tc.tool_input[:100]}")
            lines.append(f"       Output: {tc.tool_output_summary[:100]}")
        lines.append("")

        # Result
        lines.extend([
            "─" * 40,
            "  RESULT",
            "─" * 40,
            f"  {self.result_summary[:500]}",
        ])

        if self.error:
            lines.extend(["", f"  ERROR: {self.error}"])

        return "\n".join(lines)
