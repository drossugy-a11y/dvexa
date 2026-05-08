# DVexa — Modular Agent Execution Runtime

**An experimental framework for structured agent execution with tool governance and execution observability.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![Tests](https://img.shields.io/badge/tests-600%2B-passing)]()

---

## Why DVexa

Existing agent frameworks tend to focus on **orchestration** — chaining LLM calls, routing between tools, and composing prompts. DVexa focuses on the **execution layer**: what happens after a plan is made.

Designed for scenarios where you need:

- **Execution traceability** — every tool call, decision, and governance signal is recorded as an append-only event stream
- **Tool governance** — tools have lifecycle states, scoring, and policy-based selection, not just a registry
- **Feedback-driven adaptation** — execution outcomes influence tool weights and strategy preferences over time
- **Observability** — the full execution flow can be replayed and analyzed from the event store

This is not a replacement for LangChain, AutoGPT, or similar orchestration frameworks. It is a **runtime layer** designed to sit underneath or alongside them, providing structured execution guarantees that prompt-based approaches cannot offer.

---

## Architecture Overview

```
                          ┌──────────────────────────┐
                          │     Event-Sourced         │
                          │     Runtime Engine        │
                          │  (load → semantic →       │
                          │   validate → schedule →   │
                          │   govern → log)           │
                          └──────────┬───────────────┘
                                     │
               ┌─────────────────────┼─────────────────────┐
               │                     │                     │
               ▼                     ▼                     ▼
      ┌──────────────┐    ┌──────────────────┐   ┌──────────────────┐
      │    Planner    │    │   Tool Layer     │   │   Governance     │
      │  (BaseAgent)  │    │  LLM / HTTP /    │   │  SGL / ATS /     │
      │  strategist   │    │  Code / MCP /    │   │  Scheduler /     │
      │  executor     │    │  Security        │   │  ToolPolicy      │
      └──────┬───────┘    └────────┬─────────┘   └────────┬─────────┘
             │                     │                      │
             └─────────────────────┼──────────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │     EventStore       │
                        │  (append-only JSONL) │
                        └─────────────────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │  Replay / Trace /    │
                        │  Evaluation          │
                        └─────────────────────┘
```

### Core Modules

| Component | Role |
|-----------|------|
| **Kernel** | Single control loop — orchestrates plan → execute → observe cycle |
| **Planner** | LLM-based task planner with strategy generation and replanning |
| **Executor** | Rule-based tool selection and execution with error isolation |
| **CBF Guard** | Control Boundary Filter — strips non-control signals from tool outputs |
| **Governance** | SGL (intent/threat detection), ATS (behavioral testing), Scheduler (state machine) |
| **EventStore** | Append-only event persistence (JSONL) — single source of truth |
| **Evaluation** | Execution proof generation, 7-dimension capability scoring, evolution tracking |

---

## Execution Flow

```
task input
    │
    ▼
┌─────────────────┐
│  Planner         │  Generate execution strategies
│  (multiple       │  ATS-inspired strategy scoring
│   strategies)    │  Select best strategy
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Kernel          │  Execute selected strategy step by step
│  Loop            │  Tool selection via rule matching
│                  │  Error handling with retry/replan
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Guard (CBF)     │  Strip confidence/score/risk from results
│                  │  Pass only step_id + output to kernel
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Governance      │  SGL: intent + threat analysis
│  Pipeline        │  ATS: 7-stage behavioral validation
│                  │  Scheduler: state machine gating
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  EventStore      │  Append event → JSONL
│                  │  Query via trace_id
│                  │  Replay for analysis
└─────────────────┘
```

---

## Key Features

- **Multi-strategy planning** — generates and scores multiple execution strategies before selecting one
- **Tool governance system** — tools have lifecycle states (experimental → active → degraded → quarantined), scoring, and conflict detection
- **Control Boundary Filter** — kernel only receives sanitized execution results (step_id + output); all confidence/risk/score fields are stripped
- **Event-sourced execution** — every decision, risk signal, and tool call is recorded as an append-only event for full replayability
- **Execution traceability** — step-by-step reasoning traces with tool call logs, latency, and token tracking
- **Memory-influenced adaptation** — task outcomes update tool weights and strategy preferences for future executions
- **Capability scoring** — 7-dimension evaluation (planning, execution, tool usage, memory, adaptation, cost, recovery)
- **DXB compiler (experimental)** — compiles capability signals into structured execution blueprints with governance-presence locking

---

## Example Execution Trace

The evaluation module produces structured execution reports. A demo with pre-recorded data is included:

```bash
python3 -m evaluation.demo
```

Output structure:

```
DVexa Execution Proof
─────────────────────
  Task:    Design a multi-strategy portfolio analysis workflow
  Goal:    Risk-aware strategy selection with tool governance
  Success: ✓

  STRATEGIES EVALUATED
  ────────────────────
    Strategy #1: Momentum-based (ATS score: 72/100)
      Risk: 65 | Feasibility: 80 | Tool: 70
      → Rejected: higher risk exposure

    Strategy #2: Value-based (ATS score: 78/100)
      Risk: 58 | Feasibility: 85 | Tool: 75
      → Rejected: moderate score

  ▶ Strategy #3: Risk-parity (ATS score: 85/100) — SELECTED
      Risk: 72 | Feasibility: 82 | Tool: 85
      → Selected: best risk-adjusted metrics

  TOOL EXECUTION TRACE
  ────────────────────
  Step 1 [✓] http_request  — Fetch market data
  Step 2 [✓] code_executor — Calculate momentum scores
  Step 3 [✓] llm           — Strategy analysis
  Step 4 [✓] code_executor — Risk-parity optimization
  Step 5 [✓] code_executor — Monte Carlo validation
  Step 6 [✓] llm           — Generate execution plan

  CAPABILITY SCORE: 92/100
  ────────────────────
  planning_quality       100/100 (multi-strategy with 6-step decomposition)
  execution_reliability  100/100 (6/6 steps successful)
  tool_utilization       100/100 (3 tool types)
  failure_recovery        80/100 (clean execution — no failures)
  cost_efficiency         90/100 (~473 tokens/step)
```

For JSON output (machine-readable):

```bash
python3 -m evaluation.demo --format json --output eval_report.json
```

---

## Installation

```bash
git clone https://github.com/drossugy-a11y/dvexa.git
cd dvexa
pip install -r requirements.txt
```

Dependencies:
- `openai` — LLM tool client
- `fastapi` + `uvicorn` — API server (optional)

---

## Usage

### Run the evaluation demo (pre-recorded data, no LLM needed):

```bash
python3 -m evaluation.demo
```

### Run with live LLM:

Configure `.env`:

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
```

Then:

```bash
python3 -m evaluation.demo --live --task "your complex task"
```

### Start the API server:

```bash
python3 main.py
```

### Run all tests:

```bash
python3 -m pytest tests/ -q
```

---

## Design Philosophy

- **Execution-first design** — the runtime is built around the execution trace, not around prompt templates or chain definitions
- **Observability over abstraction** — every execution produces a replayable event stream; internal state is projected from events, not stored separately
- **Modular agent composition** — planner, executor, tools, and governance are separate modules with defined interfaces
- **Feedback-driven adaptation** — execution outcomes influence tool weights and strategy selection; the system is designed to improve with use
- **Conservative control flow** — the kernel only receives sanitized execution results; governance modules observe but do not modify execution

---

## Limitations

- **Experimental system** — APIs and module boundaries are still evolving
- **Not production-ready** — designed for research and experimentation; requires tuning for real workloads
- **In-memory task store** — current memory implementation is in-process; does not persist across restarts
- **Rule-based tool selection** — executor uses keyword matching for tool routing; no semantic tool retrieval
- **Single-process architecture** — no distributed execution support in the current version
- **LLM-dependent planning** — planner quality depends on the underlying model; deterministic fallback for parse failures

---

## Future Work

- **Memory compression** — more efficient storage and retrieval of historical execution data
- **Richer tool ecosystem** — expanded tool registry with automatic capability discovery
- **Improved planning strategies** — hierarchical planning with subgoal decomposition
- **Distributed execution support** — multi-process and multi-node execution
- **Semantic tool retrieval** — embedding-based tool selection as an alternative to keyword matching
- **Persistent state store** — database-backed memory and event storage

---

## License

MIT

---

*DVexa — Experimental Agent Execution Runtime*
