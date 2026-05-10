"""Streaming Executor Wrapper — 将同步 executor 调用转为流式步骤

包装 Executor.plan_task() 和 Executor.execute_step()，
在每个阶段前后通过 StepStreamer 发射步骤事件。
"""

from __future__ import annotations

import time
from typing import Any

from runtime.step_streamer import StepStreamer
from runtime.step_events import StepType


class StreamingExecutorWrapper:
    """流式执行器包装 — 旁观 executor 调用，发射步骤事件。

    不修改 executor 语义。只发射观察事件。
    """

    def __init__(self, executor: Any, step_streamer: StepStreamer):
        self._executor = executor
        self._streamer = step_streamer
        self._step_index = 0

    def plan_task(self, task_input: str) -> dict:
        """规划阶段 — 发射 PLANNING 步骤。"""
        self._streamer.planning(
            title="Generating execution plan",
            content="Decomposing task into structured steps",
        )
        start = time.time()
        result = self._executor.plan_task(task_input)
        elapsed = round(time.time() - start, 2)

        goal = result.get("goal", task_input[:60])
        steps = len(result.get("steps", []))
        self._streamer.planning(
            title=f"Plan generated ({steps} steps)",
            content=f"Goal: {goal[:120]}",
            metadata={"steps": steps, "elapsed": elapsed},
        )
        self._step_index = 0
        return result

    def execute_step(self, task: Any, step: dict, context: dict) -> dict:
        """执行步骤 — 发射 EXECUTION / TOOL_CALL / TOOL_RESULT 步骤。"""
        self._step_index += 1
        total = context.get("total_steps", 1)
        action = step.get("action", "")
        tool = step.get("tool", "")

        if tool:
            self._streamer.tool_call(
                title=f"Calling tool: {tool}",
                content=action[:120],
                metadata={"step": self._step_index, "total": total, "tool": tool},
            )
        else:
            self._streamer.execution(
                title=f"Step {self._step_index}/{total}",
                content=action[:120],
                metadata={"step": self._step_index, "total": total},
            )

        start = time.time()
        result = self._executor.execute_step(task, step, context)
        elapsed = round(time.time() - start, 2)

        output = str(result.get("output", ""))[:120]
        if tool:
            self._streamer.tool_result(
                title=f"Tool completed: {tool} ({elapsed}s)",
                content=output,
                metadata={"step": self._step_index, "tool": tool, "elapsed": elapsed},
            )
        else:
            self._streamer.execution(
                title=f"Step {self._step_index}/{total} completed ({elapsed}s)",
                content=output,
                metadata={"step": self._step_index, "elapsed": elapsed},
            )

        return result
