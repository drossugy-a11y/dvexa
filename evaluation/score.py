"""Layer 2: CapabilityScore — 7-dimension execution quality scoring.

Each dimension scored 0-100 with:
  - numerical score
  - reasoning
  - evidence reference from execution proof
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

from evaluation.proof import ExecutionProof


@dataclass
class DimensionScore:
    """Single scoring dimension."""
    name: str
    score: float  # 0-100
    weight: float  # contribution to total
    reason: str
    evidence: list[str]  # references to execution log

    @property
    def weighted(self) -> float:
        return self.score * self.weight


@dataclass
class CapabilityScore:
    """Layer 2 — structured 7-dimension capability scoring.

    Computed from an ExecutionProof, then serialized to JSON or text.
    """

    dimensions: list[DimensionScore] = field(default_factory=list)
    total_score: float = 0.0

    # ── Compute ──────────────────────────────────────────────────────────

    @classmethod
    def compute(cls, proof: ExecutionProof) -> CapabilityScore:
        """Score execution capability from proof data."""
        dims = [
            cls._score_planning(proof),
            cls._score_execution(proof),
            cls._score_tool_usage(proof),
            cls._score_memory_influence(proof),
            cls._score_adaptation(proof),
            cls._score_cost_efficiency(proof),
            cls._score_failure_recovery(proof),
        ]
        total = sum(d.weighted for d in dims) / sum(d.weight for d in dims)

        return cls(dimensions=dims, total_score=round(total, 1))

    @staticmethod
    def _score_planning(proof: ExecutionProof) -> DimensionScore:
        """1. Planning Quality — strategy diversity, decomposition quality."""
        n_strategies = len(proof.strategies)
        has_multi = n_strategies >= 2
        has_selection = any(s.selected for s in proof.strategies)
        plan_steps = 0
        for s in proof.strategies:
            steps = s.plan.get("steps", []) if isinstance(s.plan, dict) else []
            plan_steps = max(plan_steps, len(steps))

        evidence = []
        score = 30  # base

        if has_multi:
            score += 25
            evidence.append(f"Generated {n_strategies} distinct strategies")
        if plan_steps >= 3:
            score += 20
            evidence.append(f"Task decomposed into {plan_steps} steps across phases")
        if has_selection:
            score += 15
            sel = next((s for s in proof.strategies if s.selected), None)
            if sel and sel.selection_reason:
                evidence.append(f"Strategy selected: {sel.selection_reason}")
        if proof.goal:
            score += 10
            evidence.append("Goal explicitly defined from planning phase")

        return DimensionScore(
            name="planning_quality",
            score=min(score, 100),
            weight=0.20,
            reason=f"{'Multi-strategy' if has_multi else 'Single'} planning with {plan_steps} step decomposition",
            evidence=evidence,
        )

    @staticmethod
    def _score_execution(proof: ExecutionProof) -> DimensionScore:
        """2. Execution Reliability — step completion, success rate."""
        calls = proof.tool_calls
        if not calls:
            return DimensionScore(
                name="execution_reliability",
                score=0, weight=0.20,
                reason="No tool calls recorded — execution did not run",
                evidence=["No execution steps found in proof"],
            )

        success_rate = sum(1 for c in calls if c.success) / len(calls)
        n_steps = len(calls)

        evidence = []
        score = 20  # base

        if success_rate >= 0.8:
            score += 40
            evidence.append(f"Step success rate: {success_rate:.0%} ({sum(1 for c in calls if c.success)}/{n_steps})")
        elif success_rate >= 0.5:
            score += 20
            evidence.append(f"Partial success rate: {success_rate:.0%}")

        if n_steps >= 3:
            score += 20
            evidence.append(f"Completed {n_steps} execution steps")
        if proof.success:
            score += 20
            evidence.append("Task completed successfully")

        return DimensionScore(
            name="execution_reliability",
            score=min(score, 100),
            weight=0.20,
            reason=f"Step completion: {sum(1 for c in calls if c.success)}/{n_steps} ({success_rate:.0%})",
            evidence=evidence,
        )

    @staticmethod
    def _score_tool_usage(proof: ExecutionProof) -> DimensionScore:
        """3. Tool Utilization Efficiency — variety, appropriateness."""
        calls = proof.tool_calls
        if not calls:
            return DimensionScore(
                name="tool_utilization",
                score=0, weight=0.15,
                reason="No tools used during execution",
                evidence=[],
            )

        tools_used = set(c.tool for c in calls if c.tool)
        n_tools = len(tools_used)

        evidence = []
        score = 20  # base

        if n_tools >= 2:
            score += 30
            evidence.append(f"Used {n_tools} different tools: {', '.join(sorted(tools_used))}")
        elif n_tools == 1:
            score += 10
            evidence.append(f"Used 1 tool type: {next(iter(tools_used))}")

        if any("llm" in t.lower() for t in tools_used) and any(
            t not in ("llm",) for t in tools_used
        ):
            score += 25
            evidence.append("LLM + tool hybrid execution demonstrated")
        elif any("llm" in t.lower() for t in tools_used):
            score += 10

        appropriate_steps = sum(1 for c in calls if c.success or "not available" not in c.tool_output_summary.lower())
        if appropriate_steps / max(len(calls), 1) >= 0.7:
            score += 25
            evidence.append("Tool selection appropriateness: high")

        return DimensionScore(
            name="tool_utilization",
            score=min(score, 100),
            weight=0.15,
            reason=f"Used {n_tools} tool types across {len(calls)} invocations",
            evidence=evidence,
        )

    @staticmethod
    def _score_memory_influence(proof: ExecutionProof) -> DimensionScore:
        """4. Memory Influence Effectiveness — evidence of memory-driven decisions."""
        governance = proof.governance_events
        memory_refs = [
            e for e in governance
            if "memory" in str(e.get("payload", {})).lower()
            or "history" in str(e.get("payload", {})).lower()
        ]

        evidence = []
        score = 20  # base

        if memory_refs:
            score += 40
            evidence.append(f"Memory referenced in {len(memory_refs)} governance events")
        if len(proof.strategies) >= 2:
            score += 20
            evidence.append("Strategy diversity suggests memory-influenced selection")
        if proof.total_tokens > 0:
            score += 20
            evidence.append("Token tracking enabled — supports memory-informed optimization")

        return DimensionScore(
            name="memory_influence",
            score=min(score, 100),
            weight=0.10,
            reason=f"Memory references: {len(memory_refs)} events in governance trace",
            evidence=evidence,
        )

    @staticmethod
    def _score_adaptation(proof: ExecutionProof) -> DimensionScore:
        """5. Adaptive Optimization — evidence of runtime adjustment."""
        evidence = []
        score = 10  # base

        # Check for replanning or error recovery
        has_errors = bool(proof.error)
        has_replan = any(
            "replan" in str(s).lower() or "retry" in str(s).lower()
            for s in [proof.result_summary, proof.error]
        )

        if has_replan:
            score += 40
            evidence.append("Runtime replanning triggered on failure")
        if has_errors and not has_replan:
            score += 10
            evidence.append("Errors detected but no replanning evidence")
        if not has_errors and proof.success:
            score += 25
            evidence.append("Execution completed without errors — nominal path")
        if proof.governance_events:
            score += 25
            evidence.append(f"Governance events recorded ({len(proof.governance_events)} events)")

        return DimensionScore(
            name="adaptive_optimization",
            score=min(score, 100),
            weight=0.10,
            reason=f"{'Replanning demonstrated' if has_replan else 'Nominal execution'} with {len(proof.governance_events)} governance events",
            evidence=evidence,
        )

    @staticmethod
    def _score_cost_efficiency(proof: ExecutionProof) -> DimensionScore:
        """6. Cost Efficiency — token usage vs task complexity."""
        n_calls = len(proof.tool_calls)
        total_tokens = proof.total_tokens

        evidence = []
        score = 30  # base

        if total_tokens > 0:
            tokens_per_step = total_tokens / max(n_calls, 1)
            if tokens_per_step < 500:
                score += 40
                evidence.append(f"Efficient token usage: ~{tokens_per_step:.0f} tokens/step")
            elif tokens_per_step < 2000:
                score += 25
                evidence.append(f"Moderate token usage: ~{tokens_per_step:.0f} tokens/step")
            else:
                score += 10
                evidence.append(f"High token usage: ~{tokens_per_step:.0f} tokens/step")
        else:
            score += 10
            evidence.append("Token tracking not available")

        if proof.total_latency_s > 0:
            if proof.total_latency_s < 30:
                score += 20
                evidence.append(f"Low latency: {proof.total_latency_s:.1f}s total")
            else:
                score += 10
                evidence.append(f"Latency: {proof.total_latency_s:.1f}s total")

        return DimensionScore(
            name="cost_efficiency",
            score=min(score, 100),
            weight=0.10,
            reason=f"~{total_tokens} tokens across {n_calls} steps" if total_tokens > 0 else "Token data unavailable",
            evidence=evidence,
        )

    @staticmethod
    def _score_failure_recovery(proof: ExecutionProof) -> DimensionScore:
        """7. Failure Recovery Capability — error handling quality."""
        calls = proof.tool_calls
        failures = [c for c in calls if not c.success]
        has_errors = bool(proof.error)
        n_retries = has_errors  # simplified

        evidence = []
        score = 30  # base

        if not failures and proof.success:
            score += 50
            evidence.append("No failures during execution — clean run")
        elif failures:
            recovered = sum(1 for i, c in enumerate(calls) if not c.success and i + 1 < len(calls) and calls[i + 1].success)
            if recovered > 0:
                score += 35
                evidence.append(f"Recovered from {recovered} step failures")
            else:
                score += 15
                evidence.append(f"{len(failures)} failures with no recovery evidence")

        if n_retries:
            score += 20
            evidence.append("Retry mechanism available")

        return DimensionScore(
            name="failure_recovery",
            score=min(score, 100),
            weight=0.15,
            reason=f"{'Clean execution' if not failures and proof.success else f'{len(failures)} failures in execution'}",
            evidence=evidence,
        )

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "total_score": self.total_score,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "weighted": round(d.weighted, 1),
                    "reason": d.reason,
                    "evidence": d.evidence,
                }
                for d in self.dimensions
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_text(self) -> str:
        lines = [
            "=" * 60,
            "  DVexa Capability Score",
            "=" * 60,
            "",
            f"  Overall: {self.total_score}/100",
            "",
            "  Dimensional Breakdown:",
            "  ─────────────────────",
        ]
        for d in sorted(self.dimensions, key=lambda x: x.weight, reverse=True):
            bar = "█" * int(d.score / 10) + "░" * (10 - int(d.score / 10))
            lines.append(f"  {d.name:30s} {bar} {d.score:5.1f}/100 (weight: {d.weight:.0%})")
            lines.append(f"  {'':30s} {d.reason}")
            for ev in d.evidence:
                lines.append(f"  {'':30s} · {ev}")
            lines.append("")

        return "\n".join(lines)
