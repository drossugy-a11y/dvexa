from core.state import TaskStatus
from core.scheduler import Scheduler
from core.executor import Executor
from core.guard import CBF
from memory.memory_store import MemoryStore


class DVexaKernel:
    def __init__(self, scheduler: Scheduler, executor: Executor,
                 memory: MemoryStore, feedback_engine=None):
        self.scheduler = scheduler
        self.executor = executor
        self.memory = memory
        self._feedback_engine = feedback_engine

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

        # === FEEDBACK 阶段（后执行学习） ===
        if self._feedback_engine:
            trace = self._build_feedback_trace(task, task_input)
            outcome = {
                "status": "success" if task.status == TaskStatus.COMPLETED
                          else "fail",
                "error_type": task.error or "",
                "total_latency": 0.0,
            }
            self._feedback_engine.record_execution(trace, outcome)

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
        """从任务状态构建反馈执行轨迹。"""
        steps_trace = []
        exec_steps = {s["step_id"]: s for s in (task.steps or [])
                      if isinstance(s, dict) and "step_id" in s}
        for i, step in enumerate(task.plan or []):
            sid = step.get("id", i)
            record = exec_steps.get(sid, {})
            steps_trace.append({
                "step_id": sid,
                "tool": step.get("tool", record.get("tool", "")),
                "action": step.get("action", ""),
                "success": task.status == TaskStatus.COMPLETED,
                "latency": 0.0,
            })
        return {
            "task": task_input,
            "strategy_used": "",
            "steps": steps_trace,
        }
