"""Governance Evolution — 治理演化建议与安全闸门

所有 suggestion 必须经过 EvolutionGate 才能输出。
绝不能自动 apply。
"""

from governance.evolution.types import (
    EvolutionSuggestion,
    EvolutionVerdict,
    GateCheckResult,
)
from governance.evolution.strategy_evolution import StrategyEvolutionEngine
from governance.evolution.evolution_gate import EvolutionGate

__all__ = [
    "EvolutionSuggestion",
    "EvolutionVerdict",
    "GateCheckResult",
    "StrategyEvolutionEngine",
    "EvolutionGate",
]
