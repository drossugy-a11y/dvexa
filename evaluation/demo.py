"""DVexa Evaluation Demo — runs a real complex task through the system.

Usage:
    python3 -m evaluation.demo                    # demo mode (pre-recorded)
    python3 -m evaluation.demo --live             # live LLM mode
    python3 -m evaluation.demo --task "your task" # custom task
"""

from __future__ import annotations

import json
import os
import sys
import time
import argparse

from evaluation.proof import ExecutionProof, StrategyRecord, ToolCallRecord
from evaluation.score import CapabilityScore
from evaluation.evolution import EvolutionProof
from evaluation.pack import EvaluationPack

# ── Demo Mode: Pre-recorded execution data ──────────────────────────────

DEMO_TASK = """Design a multi-strategy portfolio analysis workflow for an AI investment system.

Requirements:
1. Analyze 3 different investment strategies (momentum, value, risk-parity)
2. For each strategy, evaluate risk-return profile
3. Select optimal strategy based on risk tolerance (moderate)
4. Generate execution plan with tool requirements
5. Include error handling for market data unavailability"""

DEMO_STRATEGIES = [
    {
        "description": "Momentum-based strategy with LLM-driven market analysis",
        "plan": {
            "goal": "Implement momentum investment strategy with real-time market analysis",
            "steps": [
                {"id": 1, "action": "Fetch market data for top-10 momentum stocks", "phase": "data_collection", "risk": "MEDIUM", "depends_on": []},
                {"id": 2, "action": "Calculate momentum scores using price returns", "phase": "analysis", "risk": "LOW", "depends_on": [1]},
                {"id": 3, "action": "Rank stocks by momentum score and select top-3", "phase": "selection", "risk": "MEDIUM", "depends_on": [2]},
                {"id": 4, "action": "Generate execution plan with entry/exit signals", "phase": "execution_planning", "risk": "LOW", "depends_on": [3]},
                {"id": 5, "action": "Validate strategy against historical drawdown", "phase": "validation", "risk": "HIGH", "depends_on": [4]},
            ],
        },
        "ats_score": {"overall": 72, "risk_exposure": 65, "execution_feasibility": 80, "tool_requirement": 70},
    },
    {
        "description": "Value-based strategy with code-executed fundamental analysis",
        "plan": {
            "goal": "Implement value investment strategy using fundamental ratio analysis",
            "steps": [
                {"id": 1, "action": "Retrieve financial statements for value stock candidates", "phase": "data_collection", "risk": "MEDIUM", "depends_on": []},
                {"id": 2, "action": "Calculate P/E, P/B, and dividend yield ratios via code", "phase": "analysis", "risk": "LOW", "depends_on": [1]},
                {"id": 3, "action": "Screen stocks below intrinsic value threshold", "phase": "screening", "risk": "MEDIUM", "depends_on": [2]},
                {"id": 4, "action": "Build portfolio allocation model", "phase": "execution_planning", "risk": "MEDIUM", "depends_on": [3]},
            ],
        },
        "ats_score": {"overall": 78, "risk_exposure": 58, "execution_feasibility": 85, "tool_requirement": 75},
    },
    {
        "description": "Risk-parity strategy with hybrid LLM+code implementation",
        "plan": {
            "goal": "Implement risk-parity strategy using equal risk contribution methodology",
            "steps": [
                {"id": 1, "action": "Define asset universe and correlation assumptions", "phase": "assumption", "risk": "LOW", "depends_on": []},
                {"id": 2, "action": "Calculate asset covariance matrix via code execution", "phase": "analysis", "risk": "MEDIUM", "depends_on": [1]},
                {"id": 3, "action": "Optimize weights for equal risk contribution", "phase": "optimization", "risk": "HIGH", "depends_on": [2]},
                {"id": 4, "action": "Run monte carlo simulation for robustness check", "phase": "validation", "risk": "HIGH", "depends_on": [3]},
                {"id": 5, "action": "Generate rebalancing schedule and execution plan", "phase": "execution_planning", "risk": "MEDIUM", "depends_on": [4]},
                {"id": 6, "action": "Document strategy assumptions and risk limits", "phase": "documentation", "risk": "LOW", "depends_on": [5]},
            ],
        },
        "ats_score": {"overall": 85, "risk_exposure": 72, "execution_feasibility": 82, "tool_requirement": 85},
    },
]

DEMO_TOOL_CALLS = [
    ToolCallRecord(step_id=1, action="Fetch market data for momentum analysis", tool="http_request",
                   tool_input="GET /api/market-data?screen=momentum&top=10",
                   tool_output_summary="Retrieved 10 momentum stock candidates with price data",
                   latency_s=1.2, success=True),
    ToolCallRecord(step_id=2, action="Calculate momentum scores", tool="code_executor",
                   tool_input="python: compute_momentum_scores(prices, lookback=60)",
                   tool_output_summary="Computed momentum scores: AAPL=2.3, NVDA=4.1, MSFT=1.8, ...",
                   latency_s=0.8, success=True),
    ToolCallRecord(step_id=3, action="Select top stocks by momentum", tool="llm",
                   tool_input="Select top-3 momentum stocks and justify selection",
                   tool_output_summary="Selected NVDA (momentum=4.1), AMZN (3.2), AAPL (2.3) with sector diversity",
                   latency_s=1.5, success=True),
    ToolCallRecord(step_id=4, action="Analyze risk-return for risk-parity strategy", tool="code_executor",
                   tool_input="python: calculate_risk_parity_weights(cov_matrix, assets)",
                   tool_output_summary="Risk-parity weights: [0.25, 0.20, 0.30, 0.25], expected volatility: 12.5%",
                   latency_s=1.0, success=True),
    ToolCallRecord(step_id=5, action="Run Monte Carlo validation", tool="code_executor",
                   tool_input="python: run_monte_carlo_simulation(weights, n_iterations=10000)",
                   tool_output_summary="VaR(95%): -2.3%, CVaR: -3.1%, 95% CI for returns: [-1.8%, 4.2%]",
                   latency_s=2.1, success=True),
    ToolCallRecord(step_id=6, action="Document strategy and generate execution plan", tool="llm",
                   tool_input="Generate comprehensive execution plan with risk limits and rebalancing schedule",
                   tool_output_summary="Generated execution plan with quarterly rebalancing, stop-loss at -5%, and volatility targeting",
                   latency_s=1.8, success=True),
]

DEMO_RESULT = """Completed portfolio analysis with 3 strategies evaluated. Selected risk-parity strategy (ATS score: 85/100) for lowest risk exposure. Executed 6-step plan across 3 tools (http_request, code_executor, llm). Generated rebalancing schedule. All steps completed without errors."""

DEMO_GOV_EVENTS = [
    {"stage": "semantic", "type": "decision", "payload": {"intent": "portfolio_analysis", "risk_score": 0.3, "threat_type": "none"}},
    {"stage": "validate", "type": "decision", "payload": {"passed": True, "risk_score": 0.2, "phases": ["risk_exposure", "execution_feasibility"]}},
    {"stage": "schedule", "type": "decision", "payload": {"action": "execute", "final_state": "approved"}},
    {"stage": "govern", "type": "info", "payload": {"memory_update": True, "task_id": "demo-001"}},
]


# ── Demo Data Builder ───────────────────────────────────────────────────

def build_demo_execution() -> tuple[ExecutionProof, list[dict]]:
    """Build execution proof from demo data.

    Returns (proof, memory_tasks) where memory_tasks simulates
    historical tasks from the project's in-memory store.
    """
    proof = ExecutionProof(
        task_input=DEMO_TASK,
        task_id="demo-001",
        goal="Design a risk-aware multi-strategy portfolio analysis workflow",
        total_tokens=2840,
        total_latency_s=8.4,
        estimated_cost_usd=0.0142,
        success=True,
        result_summary=DEMO_RESULT,
        governance_events=DEMO_GOV_EVENTS,
        risk_signals=[
            {"stage": "semantic", "risk_score": 0.3, "threat_type": "none"},
            {"stage": "validate", "risk_score": 0.2},
        ],
    )

    for i, s in enumerate(DEMO_STRATEGIES):
        is_selected = (i == 2)  # risk-parity wins
        reason = ""
        if is_selected:
            reason = "Risk-parity selected: lowest risk exposure (58→72) with highest tool utilization (85) and balanced execution feasibility (82)"
        elif i == 0:
            reason = "Rejected: higher risk exposure (65) and lower tool compatibility (70)"
        elif i == 1:
            reason = "Rejected: moderate score but risk-parity had better risk-adjusted metrics"

        proof.add_strategy(StrategyRecord(
            id=i + 1,
            description=s["description"],
            plan=s["plan"],
            ats_score=s["ats_score"],
            selected=is_selected,
            selection_reason=reason,
        ))

    for tc in DEMO_TOOL_CALLS:
        proof.add_tool_call(tc)

    # Simulated memory tasks for evolution proof
    memory_tasks = [
        {"task_id": "hist-001", "input": "Simple single-tool data fetch task", "status": "completed",
         "steps": [{"step_id": 1, "tool": "llm"}], "plan": []},
        {"task_id": "hist-002", "input": "Two-step analysis with code execution", "status": "completed",
         "steps": [{"step_id": 1, "tool": "llm"}, {"step_id": 2, "tool": "code_executor"}], "plan": []},
        {"task_id": "hist-003", "input": "Web research with multiple API calls", "status": "failed",
         "steps": [{"step_id": 1, "tool": "http_request"}, {"step_id": 2, "tool": "llm"}], "plan": []},
        {"task_id": "hist-004", "input": "Code generation with testing", "status": "completed",
         "steps": [{"step_id": 1, "tool": "llm"}, {"step_id": 2, "tool": "code_executor"}, {"step_id": 3, "tool": "code_executor"}], "plan": []},
        {"task_id": "hist-005", "input": "GitHub repository analysis", "status": "completed",
         "steps": [{"step_id": 1, "tool": "github"}, {"step_id": 2, "tool": "llm"}, {"step_id": 3, "tool": "llm"}], "plan": []},
    ]

    return proof, memory_tasks


# ── Live Mode ───────────────────────────────────────────────────────────

def run_live(task_input: str) -> tuple[ExecutionProof, list[dict]]:
    """Run a real task through the DVexa kernel.

    This attempts to use the configured LLM for planning and execution.
    """
    print("[evaluation] Initializing live execution...")

    try:
        from config.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
        from tools.llm_tool import LLMTool
        from tools.http_tool import HTTPTool
        from tools.code_tool import CodeExecutorTool
        from agents.base_agent import BaseAgent
        from core.executor import Executor
        from core.scheduler import Scheduler
        from memory.memory_store import MemoryStore
        from core.kernel import DVexaKernel
    except ImportError as e:
        print(f"[evaluation] Live mode unavailable (import error: {e}), falling back to demo")
        return build_demo_execution()

    # Initialize components
    llm_tool = LLMTool(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, model=LLM_MODEL)
    http_tool = HTTPTool()
    code_tool = CodeExecutorTool()

    agent = BaseAgent(llm_tool)
    tool_registry = {"llm": llm_tool, "http_request": http_tool, "code_executor": code_tool}
    executor = Executor(agent, tool_registry)
    scheduler = Scheduler()
    memory = MemoryStore()

    kernel = DVexaKernel(scheduler, executor, memory)

    # Generate multiple strategies
    print("[evaluation] Generating strategies...")
    strategy_frames = [
        "Prefer code execution for deterministic operations; use LLM only for analysis and decisions.",
        "Use LLM for all steps; leverage its reasoning capabilities throughout.",
        "Balance LLM and code tools based on step characteristics; use code for computation, LLM for semantics.",
    ]

    strategies = []
    for i, frame in enumerate(strategy_frames):
        framed_input = f"{task_input}\n\nExecution strategy: {frame}"
        try:
            plan = agent.plan(framed_input)
            strategies.append({
                "description": f"Strategy {i+1}: {frame[:60]}...",
                "plan": plan,
                "ats_score": _score_strategy(plan),
            })
            print(f"  Strategy {i+1}: {len(plan.get('steps', []))} steps planned")
        except Exception as e:
            print(f"  Strategy {i+1} failed: {e}")
            strategies.append({
                "description": f"Strategy {i+1}: LLM unavailable",
                "plan": {"goal": task_input[:80], "steps": [{"id": 1, "action": task_input, "phase": "execute", "risk": "LOW", "depends_on": []}]},
                "ats_score": {"overall": 50, "risk_exposure": 50, "execution_feasibility": 50, "tool_requirement": 50},
            })

    if not strategies:
        print("[evaluation] No strategies generated, falling back to demo")
        return build_demo_execution()

    # Select best strategy (highest ATS overall)
    best_idx = max(range(len(strategies)), key=lambda i: strategies[i]["ats_score"]["overall"])
    print(f"[evaluation] Selected strategy {best_idx + 1} (score: {strategies[best_idx]['ats_score']['overall']})")

    print("[evaluation] Executing task through kernel...")
    try:
        result = kernel.run_task(task_input)
        print(f"[evaluation] Execution complete: {result.get('status')}")
    except Exception as e:
        print(f"[evaluation] Kernel execution failed: {e}")
        result = {"task_id": "live-001", "status": "failed", "goal": "", "plan": [], "steps": [], "result": "", "error": str(e), "retry_count": 0}

    # Build execution proof
    proof = ExecutionProof(
        task_input=task_input,
        task_id=result.get("task_id", "live-001"),
        goal=result.get("goal", task_input[:80]),
        total_tokens=0,
        total_latency_s=0.0,
        success=result.get("status") == "completed",
        result_summary=str(result.get("result", ""))[:500],
        error=result.get("error", ""),
    )

    for i, s in enumerate(strategies):
        proof.add_strategy(StrategyRecord(
            id=i + 1,
            description=s["description"],
            plan=s["plan"],
            ats_score=s["ats_score"],
            selected=(i == best_idx),
            selection_reason=f"Highest ATS score: {s['ats_score']['overall']}/100",
        ))

    for step in result.get("steps", []):
        if isinstance(step, dict):
            proof.add_tool_call(ToolCallRecord(
                step_id=step.get("step_id", 0),
                action=step.get("action", ""),
                tool=step.get("tool", ""),
                tool_input=str(step.get("tool_input", ""))[:200],
                tool_output_summary=str(step.get("tool_output", ""))[:200],
                success="error" not in str(step.get("tool_output", "")).lower(),
            ))

    memory_tasks = memory.get_all()
    return proof, memory_tasks


def _score_strategy(plan: dict) -> dict:
    """Score a strategy on ATS-like dimensions."""
    steps = plan.get("steps", [])
    n_steps = len(steps)
    high_risk = sum(1 for s in steps if isinstance(s, dict) and s.get("risk") == "HIGH")
    phases = set(s.get("phase", "") for s in steps if isinstance(s, dict))

    return {
        "overall": min(50 + n_steps * 5 - high_risk * 10 + len(phases) * 3, 100),
        "risk_exposure": max(100 - high_risk * 20, 0),
        "execution_feasibility": min(60 + (n_steps >= 3) * 20 + (n_steps >= 5) * 10, 100),
        "tool_requirement": min(50 + len(phases) * 10, 100),
    }


# ── Full Evaluation Pipeline ────────────────────────────────────────────

def evaluate(task_input: str = DEMO_TASK, live: bool = False) -> EvaluationPack:
    """Full evaluation pipeline: execute → proof → score → evolution → pack."""

    t0 = time.time()

    # Layer 0: Execute (or load demo data)
    if live:
        proof, memory_tasks = run_live(task_input)
    else:
        proof, memory_tasks = build_demo_execution()

    # Layer 1: ExecutionProof (built during execution)

    # Layer 2: CapabilityScore
    score = CapabilityScore.compute(proof)

    # Layer 3: EvolutionProof
    evolution = EvolutionProof.compute(
        memory_tasks=memory_tasks,
        current_task_id=proof.task_id,
    )

    # Layer 4: EvaluationPack (aggregate all)
    pack = EvaluationPack(
        execution_proof=proof,
        capability_score=score,
        evolution_proof=evolution,
    )

    elapsed = time.time() - t0
    print(f"[evaluation] Evaluation complete in {elapsed:.2f}s")
    print(f"[evaluation] Overall score: {score.total_score}/100")

    return pack


# ── CLI Entry Point ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="DVexa Evaluation & Capability Proof System")
    parser.add_argument("--live", action="store_true", help="Run with live LLM (default: demo mode)")
    parser.add_argument("--task", type=str, default=DEMO_TASK, help="Task input for evaluation")
    parser.add_argument("--output", type=str, default="", help="Output file path (default: stdout)")
    parser.add_argument("--format", type=str, choices=["text", "json"], default="text", help="Output format")
    args = parser.parse_args()

    print("=" * 60)
    print("  DVexa Evaluation & Capability Proof System")
    print("=" * 60)
    print(f"\n  Mode: {'LIVE (real LLM)' if args.live else 'DEMO (pre-recorded data)'}")
    print(f"  Task: {args.task[:80]}...")
    print()

    pack = evaluate(task_input=args.task, live=args.live)

    # Output
    if args.format == "json" or args.output.endswith(".json"):
        output = pack.to_json()
    else:
        output = pack.to_text()

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"\n[output] Saved to {args.output}")
    else:
        print("\n" + output)


if __name__ == "__main__":
    main()
