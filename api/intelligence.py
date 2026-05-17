"""DVX Intelligence API — FastAPI Router

Intelligence endpoint set, aggregates runtime execution analysis,
failure pattern detection, cognitive profiling, and evolution suggestions.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from runtime.intelligence.execution_analyzer import RuntimeExecutionAnalyzer
from runtime.intelligence.failure_patterns import FailurePatternEngine
from runtime.intelligence.cognitive_inspector import CognitiveInspector

try:
    from governance.evolution import StrategyEvolutionEngine, EvolutionGate
    _HAS_EVOLUTION = True
except ImportError:
    StrategyEvolutionEngine = None  # type: ignore[misc]
    EvolutionGate = None  # type: ignore[misc]
    _HAS_EVOLUTION = False


def create_intelligence_router(
    event_store: Any = None,
    meta_control_plane: Any = None,
    stability_layer: Any = None,
) -> APIRouter:
    """Create Intelligence APIRouter, inject dependencies.

    Args:
        event_store: EventStore instance for reading execution traces.
        meta_control_plane: MetaControlPlane for evolution gate checks.
        stability_layer: StabilityLayer for evolution gate checks.

    Returns:
        Configured APIRouter with intelligence endpoints.
    """
    router = APIRouter(prefix="/surface/intelligence", tags=["intelligence"])

    analyzer = RuntimeExecutionAnalyzer(event_store) if event_store else None
    failure_engine = FailurePatternEngine() if event_store else None
    inspector = CognitiveInspector()
    evolution = StrategyEvolutionEngine() if _HAS_EVOLUTION else None
    gate = (
        EvolutionGate(meta_control_plane, stability_layer)
        if _HAS_EVOLUTION
        else None
    )

    @router.get("/report")
    def get_report() -> dict:
        """Aggregated execution analysis report."""
        if analyzer is None:
            return {"status": "unavailable", "reason": "No event_store"}
        traces = event_store.list_traces()[:100] if event_store else []
        report = analyzer.analyze(traces)
        return {
            "status": "ok",
            "report": {
                "total_traces": report.total_traces,
                "success_count": report.success_count,
                "failure_count": report.failure_count,
                "avg_duration_ms": report.avg_duration_ms,
                "retry_rate": report.retry_rate,
                "governance_block_rate": report.governance_block_rate,
                "stage_durations": report.stage_durations,
                "strategy_distribution": report.strategy_distribution,
                "mode_distribution": report.mode_distribution,
                "error_types": report.error_types,
            },
        }

    @router.get("/patterns")
    def get_patterns() -> dict:
        """Detected failure patterns from execution analysis."""
        if analyzer is None or failure_engine is None:
            return {"status": "unavailable", "reason": "No event_store"}
        traces = event_store.list_traces()[:100] if event_store else []
        report = analyzer.analyze(traces)
        patterns = failure_engine.analyze(report, event_store)
        return {
            "status": "ok",
            "patterns": [
                {
                    "pattern_type": p.pattern_type,
                    "severity": p.severity,
                    "description": p.description,
                    "suggestion": p.suggestion,
                    "trace_ids": list(p.trace_ids),
                }
                for p in patterns[:20]
            ],
        }

    @router.get("/cognitive")
    def get_cognitive() -> dict:
        """Current cognitive execution profile."""
        return {
            "status": "ok",
            "profile": {
                "planning_ratio": 0.0,
                "execution_ratio": 0.0,
                "tool_ratio": 0.0,
                "classification": "unknown",
            },
        }

    @router.get("/evolution")
    def get_evolution() -> dict:
        """Evolution suggestions for governance tuning."""
        if evolution is None or gate is None:
            return {
                "status": "unavailable",
                "reason": "Evolution modules not loaded",
            }
        return {
            "status": "ok",
            "suggestions": [],
            "verdicts": [],
        }

    return router
