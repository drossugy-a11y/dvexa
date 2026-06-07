"""Stock Agent Kernel — 选股分析主控制循环

简化为选股流程：
  input(研究任务) → planner(规划分析步骤) → executor(逐步执行) → guard(结果过滤) → output(分析结果)
"""

from core.state import TaskStatus
from core.scheduler import Scheduler
from core.executor import Executor
from core.guard import CBF
from memory.memory_store import MemoryStore


class StockKernel:
    def __init__(self, scheduler: Scheduler, executor: Executor,
                 memory: MemoryStore, feedback_engine=None,
                 event_store=None):
        self.scheduler = scheduler
        self.executor = executor
        self.memory = memory
        self._feedback_engine = feedback_engine
        self._event_store = event_store
        self._task_count = 0

    def run_task(self, task_input: str):
        task = self.scheduler.create_task(task_input)

        # === PLANNING 阶段 ===
        task.mark_planning()
        plan_data = self.executor.plan_task(task_input)
        task.set_plan(plan_data.get("goal", ""), plan_data.get("steps", []))

        # 记录事件
        if self._event_store:
            self._event_store.append({
                "event_type": "analysis",
                "data": {"goal": plan_data.get("goal", ""), "step_count": len(plan_data.get("steps", []))},
            })

        # === EXECUTING 阶段 ===
        task.mark_executing()
        context = {"history": []}
        steps = plan_data.get("steps", [])
        step_index = 0
        max_attempts = len(steps) * 2

        while step_index < len(steps) and len(context["history"]) < max_attempts:
            step = steps[step_index]
            context["step_index"] = step_index
            context["total_steps"] = len(steps)

            try:
                result = self.executor.execute_step(task, step, context)
                result = CBF.sanitize(result)
                context["history"].append(result)
                step_index += 1
            except Exception as e:
                task.increment_retry()
                if task.can_retry():
                    task.mark_waiting()
                else:
                    replan = self.executor.agent.replan(task_input, step, str(e))
                    if replan and replan.get("steps"):
                        task.set_plan(replan["goal"], replan["steps"])
                        task.mark_executing()
                        steps = replan["steps"]
                        step_index = 0
                        context["history"] = []
                    else:
                        task.mark_failed(str(e))
                        break

        if task.status != TaskStatus.FAILED:
            final_result = "\n".join(
                f"步骤{r['step_id']}: {str(r.get('output', ''))[:300]}"
                for r in context["history"]
            )
            task.mark_completed(final_result)

        self.memory.save(task)

        # === FEEDBACK 阶段 ===
        if self._feedback_engine:
            trace = self._build_feedback_trace(task, task_input)
            outcome = {
                "status": "success" if task.status == TaskStatus.COMPLETED else "fail",
                "error_type": task.error or "",
            }
            self._feedback_engine.record_execution(trace, outcome)

        self._task_count += 1

        return {
            "task_id": task.id,
            "status": task.status.value,
            "goal": task.plan_goal,
            "plan": task.plan,
            "steps": task.steps,
            "result": task.result,
            "retry_count": task.retry_count,
        }

    def _build_feedback_trace(self, task, task_input: str) -> dict:
        steps_trace = []
        for i, step in enumerate(task.plan or []):
            sid = step.get("id", i)
            steps_trace.append({
                "step_id": sid,
                "tool": step.get("tool", ""),
                "action": step.get("action", ""),
                "success": task.status == TaskStatus.COMPLETED,
                "latency": 0.0,
            })
        return {"task": task_input, "strategy_used": "", "steps": steps_trace}
