"""DVexa Evaluation & Capability Proof System.

Layers:
  - ExecutionProof:  captures complete execution trace with tool calls, strategies, decisions
  - CapabilityScore:  7-dimension scoring (0-100) with evidence references
  - EvolutionProof:   memory-driven adaptation and policy changes over time
  - EvaluationPack:   aggregates all layers into structured dual-format output
"""

from evaluation.proof import ExecutionProof
from evaluation.score import CapabilityScore
from evaluation.evolution import EvolutionProof
from evaluation.pack import EvaluationPack

__all__ = [
    "ExecutionProof",
    "CapabilityScore",
    "EvolutionProof",
    "EvaluationPack",
]
