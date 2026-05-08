# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

DVexa is an experimental **agent execution runtime** with a layered architecture. The core design principle: a single control loop retains execution authority while governance modules observe and score without modifying control flow.

### Layer Architecture

**Core (stable base layer):**
- `core/kernel.py` — single control loop + optional FeedbackEngine post-execution hook
- `core/executor.py` — plan → execute → result
- `core/guard.py` — Control Boundary Filter (strips non-control signals from execution results)
- `agents/base_agent.py` — LLM-based task planner

**Governance (decision + learning):**
- `governance/governance_kernel.py` — Unified engine: `process(task, plan) → {filtered_plan, strategy, decisions}`, 5 checkpoints (ToolPolicy→ATS→SkillScore→Lifecycle→StrategyOverride), 4 deterministic strategies
- `governance/feedback_engine.py` — Closed-loop learning: post-execution SkillScore/preference/stat updates, no LLM
- `governance/skill_governor.py` + `skill_score.py` + `lifecycle.py` — Scoring, lifecycle, recovery
- `governance/tool_policy.py` — Binary allow/deny policy
- `governance/decision_layer.py` + `strategy_layer.py` — Thin wrappers (deprecated, backward compat)

**Extensible modules:**
- `runtime/` — Event-Sourced Runtime Engine (orchestration layer)
- `capabilities/` — SkillRegistry, CapabilityRouter, individual skills
- `governance/stabilizer.py` — Convergence layer: caps steps, dedup decisions, enforces feedback boundaries
- `evaluation/` — Execution proof generation, capability scoring, evolution tracking
- `insight/` — System analysis, drift detection
- `external/` — External agent sandboxing, capability analysis
- `report/` — Post-execution metrics collection
- `tools/` — Tool base classes (LLM, HTTP, Code, MCP)

### Event-Sourced Runtime

The runtime uses an Event-Sourced architecture — all execution output is stored as Events in an append-only EventStore:

```
input → DVXRuntimeEngine.run()
         │
         ▼  Event × N
         │
    EventStore.append() → JSONL persistence
         │
         ▼
    RuntimeContext (input + events[] + metadata)
         │
         ▼  Computed properties from event projection
    ctx.passed, ctx.risk_score, etc.
```

**Key constraints:**
- `Event` is the only persistence structure
- `EventStore` is append-only — single source of truth
- Governance modules output `Event` via transformer methods
- `DVXReplayEngine` reads entirely from EventStore

### Execution Flow

```
                            DVX Runtime Engine
                            ===================
input → DVXRuntimeEngine.run()
         │
    ┌── Stage 1: LOAD ────── Event
    ├── Stage 2: SEMANTIC ─── Event (governance intent/threat detection)
    ├── Stage 3: VALIDATE ─── Event (behavioral testing)
    ├── Stage 4: SCHEDULE ─── Event list (state machine gating)
    ├── Stage 5: GOVERN ───── Event (governance snapshot)
    └── Stage 6: LOG ──────── Event → EventStore
         │
         ▼
    RuntimeContext (events + metadata)
         │
         ├── ExecutionTrace (event-based query)
         └── ReplayEngine (EventStore replay + diff)
```

### Full Execution Flow (production path)

```
Input → DVexaKernel.run_task()
         │
         ├── Scheduler.create_task()
         ├── Executor.plan_task()           # BaseAgent plans
         │     ├── ComplexityBudget        # PRE: structure + limit
         │     ├── CostModel               # PRE: economic constraint
         │     ├── GovernanceKernel.inject() # 5 checkpoints filter plan
         │     └── Stabilizer                # POST: convergence fallback
         ├── Executor.execute_step() × N     # each step through governance
         ├── CBF.sanitize()                  # strip non-control signals
         ├── MemoryStore.save()
         ├── GovernanceFeedbackEngine.record_execution()  # post-learning
         └── return result
```

### Governance Module Event Pattern (runtime path)

| Module | Role | Event Method |
|--------|------|-------------|
| DVXLoader | Parse `ACTION { ... }` input | `parse() → Event` |
| SemanticGovernanceLayer | Intent + threat detection | `analyze_event(event) → Event` |
| AssimilationTestSystem | 7-stage behavioral validation | `run_event(event) → Event` |
| AssimilationScheduler | State machine risk gating | `process_event(event) → list[Event]` |

## Commands

```bash
# Run all tests
python3 -m pytest tests/ -q

# Run single test file
python3 -m pytest tests/test_governance.py -v

# Run governance kernel tests
python3 -m pytest tests/test_governance_kernel.py -v

# Run feedback engine tests
python3 -m pytest tests/test_feedback_engine.py -v

# Run stabilizer tests
python3 -m pytest tests/test_governance_stabilizer.py -v

# Run complexity budget tests
python3 -m pytest tests/test_complexity_budget.py -v

# Run cost model tests
python3 -m pytest tests/test_governance_cost_model.py -v

# Run global optimization tests
python3 -m pytest tests/test_global_optimization.py -v

# Run stability layer tests
python3 -m pytest tests/test_stability_layer.py -v

# Run strategy layer tests
python3 -m pytest tests/test_strategy_layer.py -v

# Run decision layer tests
python3 -m pytest tests/test_decision_layer.py -v

# Run with coverage
python3 -m pytest tests/ --cov=. --cov-report=term

# Run Evaluation demo (pre-recorded demo data)
python3 -m evaluation.demo

# Run Evaluation demo with live LLM
python3 -m evaluation.demo --live

# Save evaluation report to file
python3 -m evaluation.demo --output report.json --format json

# Start API server
python3 main.py

# Run integration tests
python3 scripts/test_runtime_engine.py
python3 scripts/integration_test_v1.py

# Install dependencies
pip install -r requirements.txt
```

## Codebase Structure

| Directory | Purpose |
|-----------|---------|
| `core/` | Control loop, executor, CBF guard, scheduler |
| `agents/` | LLM-based task planner (BaseAgent) |
| `runtime/` | Event-Sourced Runtime Engine |
| `capabilities/` | Skill definitions, registry, router |
| `governance/` | GovernanceKernel (unified decision), ComplexityBudget (structure), CostModel (economic), GlobalOptimizationLoop (system learning), StabilityLayer (drift guard + rollback + safety lock), Stabilizer (convergence), FeedbackEngine (learning), SGL, ATS, Scheduler, lifecycle, scoring, policy |
| `evaluation/` | Execution proof, capability scoring, evolution tracking |
| `insight/` | System analysis, drift detection |
| `external/` | External agent sandboxing, assimilation analysis |
| `report/` | Metrics collection, report formatting |
| `memory/` | In-memory task store |
| `tools/` | Tool base classes (LLM, HTTP, Code, MCP, security scanner) |
| `config/` | Configuration from .env |
| `api/` | FastAPI server |
| `scripts/` | Integration tests, utility scripts |
| `tests/` | Pytest test suite |
| `compiler_v2/` | Experimental DXB compiler (capability IR → execution blueprint) |

## Test Conventions

- Tests use `pytest` with plain `assert` (no unittest)
- Organize by feature class: `class TestFeature:` with `def test_behavior(self):`
- Test helpers defined as module-level classes
- New features require accompanying tests
