from core.state import TaskStatus
from core.scheduler import Scheduler
from core.executor import Executor
from core.guard import CBF
from memory.memory_store import MemoryStore


class DVexaKernel:
    def __init__(self, scheduler: Scheduler, executor: Executor, memory: MemoryStore):
        self.scheduler = scheduler
        self.executor = executor
        self.memory = memory

    def run_task(self, task_input: str):
        task = self.scheduler.create_task(task_input)

        # === PLANNING 阶段 ===
        task.mark_planning()
        plan_data = self.executor.plan_task(task_input)
        task.set_plan(plan_data.get("goal", ""), plan_data.get("steps", []))

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
                # CBF: 剥离所有非控制信号（confidence/score/status/tool等）
                # 确保 kernel 只看"事实"，不看"评价"
                result = CBF.sanitize(result)
                context["history"].append(result)
                step_index += 1
            except Exception as e:
                task.increment_retry()
                if task.can_retry():
                    task.mark_waiting()
                else:
                    replan = self.executor.agent.replan(
                        task_input, step, str(e)
                    )
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
                f"步骤{r['step_id']}: {str(r.get('output',''))[:300]}"
                for r in context["history"]
            )
            task.mark_completed(final_result)

        self.memory.save(task)
        return {
            "task_id": task.id,
            "status": task.status.value,
            "goal": task.plan_goal,
            "plan": task.plan,
            "steps": task.steps,
            "result": task.result,
            "retry_count": task.retry_count,
        }
