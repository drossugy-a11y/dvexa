"""Layer 3: EvolutionProof — memory-driven adaptation and policy changes.

Tracks:
  - How historical memory influenced the current execution
  - Strategy preference / weight changes across runs
  - Tool policy adjustments (up/down-weighting)
  - Governance module state changes
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class PolicyDelta:
    """A recorded change in a governance policy or weight."""
    component: str        # e.g. "tool_policy", "skill_score", "ats_threshold"
    field: str            # e.g. "code_executor.weight", "risk_threshold"
    before: Any
    after: Any
    reason: str = ""


@dataclass
class MemoryInfluence:
    """How a specific historical task influenced the current execution."""
    source_task_id: str
    source_input_summary: str
    influence_type: str     # "strategy_shift", "weight_change", "tool_preference"
    description: str


@dataclass
class EvolutionProof:
    """Layer 3 — memory-driven adaptation and policy evolution.

    Populated from MemoryStore history + governance state diffing.
    """

    # Memory influence
    memory_influences: list[MemoryInfluence] = field(default_factory=list)
    historical_task_count: int = 0

    # Policy changes
    policy_deltas: list[PolicyDelta] = field(default_factory=list)

    # Strategy preference changes
    strategy_preference_shifts: list[dict] = field(default_factory=list)

    # Current state snapshot
    governance_state: dict = field(default_factory=dict)
    tool_policy_state: dict = field(default_factory=dict)

    compiled_at: float = 0.0

    def __post_init__(self):
        if not self.compiled_at:
            self.compiled_at = time.time()

    # ── Builders ──────────────────────────────────────────────────────────

    @classmethod
    def compute(
        cls,
        memory_tasks: list[dict],
        tool_policy_state: dict | None = None,
        governance_snapshot: dict | None = None,
        current_task_id: str | None = None,
    ) -> EvolutionProof:
        """Compute evolution proof from MemoryStore + governance data."""
        proof = cls(
            historical_task_count=len(memory_tasks),
            tool_policy_state=tool_policy_state or {},
            governance_state=governance_snapshot or {},
        )

        # Detect memory influences on current task
        influences = cls._detect_influences(memory_tasks, current_task_id)
        proof.memory_influences = influences

        # Detect strategy preference shifts across history
        shifts = cls._detect_strategy_shifts(memory_tasks)
        proof.strategy_preference_shifts = shifts

        # Detect policy deltas in tool policy
        if tool_policy_state:
            deltas = cls._detect_policy_deltas(tool_policy_state)
            proof.policy_deltas = deltas

        return proof

    @staticmethod
    def _detect_influences(
        tasks: list[dict], current_task_id: str | None
    ) -> list[MemoryInfluence]:
        """Find historical tasks that influenced the current execution."""
        influences: list[MemoryInfluence] = []

        # Track tool preference shifts across history
        tool_usage_history: dict[str, int] = {}
        for t in tasks:
            if t.get("task_id") == current_task_id:
                continue
            for step in (t.get("steps") or t.get("plan") or []):
                if isinstance(step, dict):
                    tool = step.get("tool", "")
                    if tool:
                        tool_usage_history[tool] = tool_usage_history.get(tool, 0) + 1

        if tool_usage_history:
            most_used = max(tool_usage_history, key=tool_usage_history.get)
            influences.append(MemoryInfluence(
                source_task_id="historical",
                source_input_summary="aggregated task history",
                influence_type="tool_preference",
                description=f"Historical data shows '{most_used}' as most frequently used tool ({tool_usage_history[most_used]} times)",
            ))

        # Find failure-recovery patterns
        failed_tasks = [
            t for t in tasks
            if t.get("status") == "failed" and t.get("task_id") != current_task_id
        ]
        if failed_tasks:
            influences.append(MemoryInfluence(
                source_task_id=failed_tasks[-1]["task_id"],
                source_input_summary=str(failed_tasks[-1].get("input", ""))[:100],
                influence_type="strategy_shift",
                description=f"Previous task failure ({failed_tasks[-1].get('task_id')}) influenced retry/replanning strategy",
            ))

        return influences

    @staticmethod
    def _detect_strategy_shifts(tasks: list[dict]) -> list[dict]:
        """Detect changes in strategy patterns across execution history."""
        shifts: list[dict] = []

        # Track tool usage ratios
        llm_only = 0
        tool_hybrid = 0
        for t in tasks:
            steps = t.get("steps") or t.get("plan") or []
            tools_in_task = set()
            for s in steps:
                if isinstance(s, dict) and s.get("tool"):
                    tools_in_task.add(s.get("tool"))
            if len(tools_in_task) <= 1:
                llm_only += 1
            else:
                tool_hybrid += 1

        total = llm_only + tool_hybrid
        if total >= 2:
            shifts.append({
                "pattern": "tool_diversity",
                "llm_only_ratio": round(llm_only / total, 2),
                "hybrid_ratio": round(tool_hybrid / total, 2),
                "description": f"Of {total} historical tasks, {tool_hybrid} used multi-tool strategy vs {llm_only} LLM-only",
            })

        # Track success rate trend
        completed = [t for t in tasks if t.get("status") == "completed"]
        failed = [t for t in tasks if t.get("status") == "failed"]
        if completed or failed:
            shifts.append({
                "pattern": "success_rate",
                "completed": len(completed),
                "failed": len(failed),
                "rate": round(len(completed) / max(len(completed) + len(failed), 1), 2),
                "description": f"Historical success rate: {len(completed)}/{len(completed) + len(failed)}",
            })

        return shifts

    @staticmethod
    def _detect_policy_deltas(tool_policy: dict) -> list[PolicyDelta]:
        """Extract policy changes from tool policy state."""
        deltas: list[PolicyDelta] = []

        allowed = tool_policy.get("allowed_tools", {})
        denied = tool_policy.get("denied_tools", [])

        if allowed:
            for tool_name, weight in allowed.items():
                if isinstance(weight, (int, float)) and weight < 1.0:
                    deltas.append(PolicyDelta(
                        component="tool_policy",
                        field=f"{tool_name}.weight",
                        before=1.0,
                        after=weight,
                        reason="Tool down-weighted by governance policy",
                    ))

        if denied:
            deltas.append(PolicyDelta(
                component="tool_policy",
                field="denied_tools",
                before=[],
                after=denied,
                reason=f"Tools restricted: {', '.join(denied)}",
            ))

        return deltas

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "historical_task_count": self.historical_task_count,
            "memory_influences": [
                {
                    "source": inf.source_task_id,
                    "type": inf.influence_type,
                    "description": inf.description,
                }
                for inf in self.memory_influences
            ],
            "strategy_preference_shifts": self.strategy_preference_shifts,
            "policy_deltas": [
                {
                    "component": d.component,
                    "field": d.field,
                    "before": d.before,
                    "after": d.after,
                    "reason": d.reason,
                }
                for d in self.policy_deltas
            ],
            "compiled_at": self.compiled_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def to_text(self) -> str:
        lines = [
            "=" * 60,
            "  DVexa Evolution Proof",
            "=" * 60,
            "",
            f"  Historical tasks analyzed: {self.historical_task_count}",
            "",
        ]

        if self.memory_influences:
            lines.extend(["─" * 40, "  MEMORY INFLUENCES", "─" * 40])
            for inf in self.memory_influences:
                lines.append(f"  [{inf.influence_type}] {inf.description}")
            lines.append("")

        if self.strategy_preference_shifts:
            lines.extend(["─" * 40, "  STRATEGY PREFERENCE SHIFTS", "─" * 40])
            for shift in self.strategy_preference_shifts:
                desc = shift.get("description", "")
                lines.append(f"  · {desc}")
            lines.append("")

        if self.policy_deltas:
            lines.extend(["─" * 40, "  POLICY CHANGES", "─" * 40])
            for d in self.policy_deltas:
                lines.append(f"  [{d.component}] {d.field}: {d.before} → {d.after}")
                lines.append(f"       Reason: {d.reason}")
            lines.append("")

        return "\n".join(lines)
