"""Layer 4: EvaluationPack — aggregates all 3 layers into structured output.

Generates:
  - Aggregated JSON (machine-readable)
  - Human-readable text report
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from evaluation.proof import ExecutionProof
from evaluation.score import CapabilityScore
from evaluation.evolution import EvolutionProof


@dataclass
class EvaluationPack:
    """Complete evaluation pack — proof + score + evolution.

    Dual-format output: JSON (machine) + text (human).
    """

    execution_proof: ExecutionProof
    capability_score: CapabilityScore
    evolution_proof: EvolutionProof

    generated_at: float = 0.0

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = time.time()

    # ── Aggregated Output ────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "pack_metadata": {
                "generated_at": self.generated_at,
                "version": "dvexa-evaluation-v1",
            },
            "execution_proof": self.execution_proof.to_dict(),
            "capability_score": self.capability_score.to_dict(),
            "evolution_proof": self.evolution_proof.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def to_text(self) -> str:
        sections = [
            self.execution_proof.to_text(),
            "",
            self.capability_score.to_text(),
            "",
            self.evolution_proof.to_text(),
        ]
        return "\n".join(sections)

    # ── Summary Statistics ───────────────────────────────────────────────

    def summary(self) -> dict:
        """Quick summary for reporting."""
        return {
            "task": self.execution_proof.task_input[:100],
            "success": self.execution_proof.success,
            "overall_score": self.capability_score.total_score,
            "tool_calls": len(self.execution_proof.tool_calls),
            "strategies_evaluated": len(self.execution_proof.strategies),
            "historical_tasks": self.evolution_proof.historical_task_count,
            "latency_s": round(self.execution_proof.total_latency_s, 2),
        }
