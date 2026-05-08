"""OpenCode Repository Analyzer — Phase 1

静态分析 sst/opencode 源码结构，提取架构模式。
不执行外部代码，不联网，只读文件系统。

Output:
    {
        "planner_patterns": [...],
        "execution_patterns": [...],
        "context_patterns": [...],
        "memory_patterns": [...],
        "tool_patterns": [...],
        "runtime_patterns": [...],
        "risk_patterns": [...],
        "recommended_adoptions": [...]
    }
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


class OpenCodeAnalyzer:
    """OpenCode 源码结构分析器。

    只做: 分析文件结构、识别架构模块、提取设计约定
    不做: 执行代码、联网、修改文件
    """

    def __init__(self):
        self._findings: dict[str, Any] = {}
        self._file_index: dict[str, list[str]] = {}

    def analyze_repo(self, repo_path: str) -> dict:
        """主入口：分析仓库并返回结构化结果。

        Args:
            repo_path: 本地仓库路径

        Returns:
            结构化分析字典
        """
        root = Path(repo_path)
        if not root.exists():
            return {"error": f"Path not found: {repo_path}"}

        self._index_files(root)

        return {
            "repository": self._analyze_repository_meta(root),
            "planner_patterns": self._extract_planner_patterns(root),
            "execution_patterns": self._extract_execution_patterns(root),
            "context_patterns": self._extract_context_patterns(root),
            "memory_patterns": self._extract_memory_patterns(root),
            "tool_patterns": self._extract_tool_patterns(root),
            "runtime_patterns": self._extract_runtime_patterns(root),
            "risk_patterns": self._identify_risks(root),
            "recommended_adoptions": self._recommend_adoptions(),
            "architecture_summary": self._summarize_architecture(root),
        }

    # ═══════════════════════════════════════════════════════════════════
    # Index
    # ═══════════════════════════════════════════════════════════════════

    def _index_files(self, root: Path):
        """建立文件索引。"""
        for f in root.rglob("*.ts"):
            if ".git/" in str(f) or "node_modules/" in str(f):
                continue
            d = str(f.parent.relative_to(root))
            self._file_index.setdefault(d, []).append(f.name)

    # ═══════════════════════════════════════════════════════════════════
    # Repository Meta
    # ═══════════════════════════════════════════════════════════════════

    def _analyze_repository_meta(self, root: Path) -> dict:
        pkg = self._read_json(root / "package.json")
        return {
            "name": pkg.get("name", "unknown"),
            "language": "TypeScript",
            "runtime": "Bun",
            "framework": "Effect-TS",
            "package_manager": pkg.get("packageManager", "unknown"),
            "is_monorepo": "workspaces" in pkg,
            "workspaces": list(pkg.get("workspaces", {}).get("packages", [])),
        }

    def _summarize_architecture(self, root: Path) -> dict:
        src = root / "packages" / "opencode" / "src"
        modules = {}
        if src.exists():
            for d in sorted(src.iterdir()):
                if d.is_dir():
                    ts_files = list(d.rglob("*.ts"))
                    modules[d.name] = len(ts_files)

        return {
            "top_level_modules": list(modules.keys()),
            "module_file_counts": modules,
            "core_runtime_modules": [
                m for m in modules
                if m in ("session", "tool", "agent", "project", "server")
            ],
            "control_modules": [
                m for m in modules
                if m in ("permission", "config", "control-plane", "auth", "skill")
            ],
            "infra_modules": [
                m for m in modules
                if m in ("storage", "sync", "file", "pty", "bus")
            ],
        }

    # ═══════════════════════════════════════════════════════════════════
    # Pattern Extractors
    # ═══════════════════════════════════════════════════════════════════

    def _extract_planner_patterns(self, root: Path) -> list[dict]:
        patterns = []
        src = root / "packages" / "opencode" / "src"

        # session/todo.ts — task decomposition
        patterns.append({
            "source": "session/todo.ts",
            "pattern": "task-todo-decomposition",
            "description": "Planner produces structured task list with status tracking",
            "mechanism": "LLM generates {id, status, content} entries managed via todos",
        })

        # session/plan.ts — explicit planning (check if exists)
        plan_files = ["session/plan.ts", "tool/plan.ts"]
        for pf in plan_files:
            if (src / pf).exists():
                patterns.append({
                    "source": pf,
                    "pattern": "explicit-plan-tool",
                    "description": "Dedicated plan tool for pre-execution planning",
                    "mechanism": "Tool forces LLM to produce structured plan before acting",
                })
                break

        # session/instruction.ts — system instructions
        if (src / "session/instruction.ts").exists():
            patterns.append({
                "source": "session/instruction.ts",
                "pattern": "layered-system-instructions",
                "description": "Multi-layer system prompts with priority ordering",
                "mechanism": "Instructions composed from multiple config sources, merged at runtime",
            })

        return patterns

    def _extract_execution_patterns(self, root: Path) -> list[dict]:
        patterns = []
        src = root / "packages" / "opencode" / "src"

        # session/retry.ts — retry logic
        if (src / "session/retry.ts").exists():
            patterns.append({
                "source": "session/retry.ts",
                "pattern": "execution-retry-with-exponential-backoff",
                "description": "Failed steps retried with configurable backoff",
                "mechanism": "Retry counter per step, replan on exhaustion",
            })

        # session/compaction.ts — context compression
        if (src / "session/compaction.ts").exists():
            patterns.append({
                "source": "session/compaction.ts",
                "pattern": "context-compaction-mid-execution",
                "description": "Context window management during long executions",
                "mechanism": "Summarizes completed steps, prunes old messages, keeps recent context",
            })

        # session/processor.ts — execution pipeline
        if (src / "session/processor.ts").exists():
            patterns.append({
                "source": "session/processor.ts",
                "pattern": "streaming-tool-execution-pipeline",
                "description": "Streaming LLM response → tool call parsing → execution → result streaming",
                "mechanism": "Single processor handles parse → execute → stream loop",
            })

        return patterns

    def _extract_context_patterns(self, root: Path) -> list[dict]:
        patterns = []
        src = root / "packages" / "opencode" / "src"

        # session/overflow.ts — overflow handling
        if (src / "session/overflow.ts").exists():
            patterns.append({
                "source": "session/overflow.ts",
                "pattern": "context-overflow-detection-and-handling",
                "description": "Detect and respond to context window overflow",
                "mechanism": "Monitors token count, triggers compaction or truncation on overflow",
            })

        # tool/truncation-dir.ts — directory truncation
        if (src / "tool/truncation-dir.ts").exists():
            patterns.append({
                "source": "tool/truncation-dir.ts",
                "pattern": "directory-context-truncation",
                "description": "Intelligently truncate large directory listings for context",
                "mechanism": "Prioritize important files, summarize large directories",
            })

        # session/summary.ts — summarization
        if (src / "session/summary.ts").exists():
            patterns.append({
                "source": "session/summary.ts",
                "pattern": "execution-summary-on-context-pressure",
                "description": "Generate summaries of completed work when context fills",
                "mechanism": "Summarize past steps into compressed form, freeing context space",
            })

        return patterns

    def _extract_memory_patterns(self, root: Path) -> list[dict]:
        patterns = []
        src = root / "packages" / "opencode" / "src"

        # storage/storage.ts — persistence
        if (src / "storage/storage.ts").exists():
            patterns.append({
                "source": "storage/storage.ts",
                "pattern": "sqlite-backed-session-persistence",
                "description": "All session state persisted to SQLite",
                "mechanism": "Drizzle ORM + SQLite for structured persistence",
            })

        # session/message.ts — message history
        if (src / "session/message.ts").exists():
            patterns.append({
                "source": "session/message.ts",
                "pattern": "structured-message-history-with-roles",
                "description": "Full message history with structured role/part model",
                "mechanism": "Messages stored as typed parts (text, tool_call, tool_result)",
            })

        # session/session.ts — session lifecycle
        if (src / "session/session.ts").exists():
            patterns.append({
                "source": "session/session.ts",
                "pattern": "session-lifecycle-state-machine",
                "description": "Session has explicit state transitions",
                "mechanism": "Session moves through states: idle → running → waiting → done",
            })

        return patterns

    def _extract_tool_patterns(self, root: Path) -> list[dict]:
        patterns = []
        src = root / "packages" / "opencode" / "src"

        # tool/registry.ts — tool registry
        if (src / "tool/registry.ts").exists():
            patterns.append({
                "source": "tool/registry.ts",
                "pattern": "centralized-tool-registry-with-schema",
                "description": "All tools registered centrally with Zod schemas",
                "mechanism": "Registry maps tool names to {schema, execute, description}",
            })

        # tool/tool.ts — tool base
        if (src / "tool/tool.ts").exists():
            patterns.append({
                "source": "tool/tool.ts",
                "pattern": "typed-tool-interface-with-validation",
                "description": "Every tool has typed input/output validated by Zod",
                "mechanism": "Tool = {name, schema, execute(input) → output}",
            })

        # tool/schema.ts — shared schema
        if (src / "tool/schema.ts").exists():
            patterns.append({
                "source": "tool/schema.ts",
                "pattern": "unified-tool-schema-convention",
                "description": "Single source of truth for tool schema definitions",
                "mechanism": "Shared schema types ensure consistency across all tools",
            })

        # tool/task.ts — sub-agent delegation
        if (src / "tool/task.ts").exists():
            patterns.append({
                "source": "tool/task.ts",
                "pattern": "sub-agent-task-delegation",
                "description": "Main agent can spawn sub-agents for isolated tasks",
                "mechanism": "Task tool spawns new session context with limited scope",
            })

        return patterns

    def _extract_runtime_patterns(self, root: Path) -> list[dict]:
        patterns = []
        src = root / "packages" / "opencode" / "src"

        # effect/runner.ts — runner
        if (src / "effect/runner.ts").exists():
            patterns.append({
                "source": "effect/runner.ts",
                "pattern": "effect-ts-fiber-based-execution",
                "description": "Runtime uses Effect-TS fibers for concurrent execution",
                "mechanism": "Effect.runPromise with fiber supervision for lifecycle",
            })

        # session/run-state.ts — run state
        if (src / "session/run-state.ts").exists():
            patterns.append({
                "source": "session/run-state.ts",
                "pattern": "observable-run-state-machine",
                "description": "Runtime state exposed as observable state machine",
                "mechanism": "State transitions broadcast to subscribers",
            })

        # bus/ — event bus
        if (src / "bus").exists():
            patterns.append({
                "source": "bus/",
                "pattern": "internal-event-bus-for-decoupling",
                "description": "Modules communicate via typed event bus, not direct calls",
                "mechanism": "Bus<TEvent> with typed publish/subscribe",
            })

        return patterns

    def _identify_risks(self, root: Path) -> list[dict]:
        risks = []
        src = root / "packages" / "opencode" / "src"

        # Multi-agent complexity
        if (src / "tool/task.ts").exists():
            risks.append({
                "type": "multi-agent-spawn",
                "severity": "medium",
                "description": "Sub-agent spawning could lead to uncontrolled agent proliferation",
                "dvexa_equivalent": "No sub-agent spawning in DVexa — Kernel is single control point",
            })

        # Effect-TS coupling
        if (src / "effect").exists():
            risks.append({
                "type": "framework-coupling",
                "severity": "high",
                "description": "Heavy coupling to Effect-TS — not portable to Python/DVexa",
                "dvexa_equivalent": "DVexa uses direct Python control flow, not monadic effects",
            })

        # Tool autonomous execution
        risks.append({
            "type": "tool-autonomy",
            "severity": "high",
            "description": "Tools like edit/write/shell have file system write access",
            "dvexa_equivalent": "DVexa CBF strips non-control signals; tool access is governance-gated",
        })

        return risks

    def _recommend_adoptions(self) -> list[dict]:
        """基于所有分析结果生成推荐采纳项。"""
        recommendations = []

        recommendations.append({
            "pattern": "context-compaction-mid-execution",
            "category": "execution",
            "priority": "high",
            "reason": "DVexa currently has no context compaction during long executions",
            "dvexa_target": "core/executor.py — add compaction trigger on step_count > N",
            "effort": "medium",
            "risk": "low",
        })

        recommendations.append({
            "pattern": "execution-retry-with-exponential-backoff",
            "category": "execution",
            "priority": "medium",
            "reason": "DVexa retry is flat; exponential backoff would improve resilience",
            "dvexa_target": "core/executor.py — retry with backoff multiplier",
            "effort": "low",
            "risk": "low",
        })

        recommendations.append({
            "pattern": "unified-tool-schema-convention",
            "category": "tool",
            "priority": "medium",
            "reason": "OpenCode's Zod-validated tool schemas are more rigorous than DVexa's dict-based tools",
            "dvexa_target": "tools/ — add typed schema validation layer",
            "effort": "high",
            "risk": "medium",
        })

        recommendations.append({
            "pattern": "session-lifecycle-state-machine",
            "category": "memory",
            "priority": "medium",
            "reason": "Explicit session state machine would improve DVexa's task lifecycle tracking",
            "dvexa_target": "core/state.py — enrich TaskState with more transitions",
            "effort": "low",
            "risk": "low",
        })

        recommendations.append({
            "pattern": "internal-event-bus-for-decoupling",
            "category": "runtime",
            "priority": "low",
            "reason": "Event bus decoupling is useful but conflicts with DVexa single-kernel design",
            "dvexa_target": "evaluation — only for introspection, not control flow",
            "effort": "high",
            "risk": "high",
        })

        return recommendations

    # ═══════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text()
        except Exception:
            return ""
