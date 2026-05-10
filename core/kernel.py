from core.state import TaskStatus
from core.scheduler import Scheduler
from core.executor import Executor
from core.guard import CBF
from memory.memory_store import MemoryStore


class DVexaKernel:
    def __init__(self, scheduler: Scheduler, executor: Executor,
                 memory: MemoryStore, feedback_engine=None,
                 global_optimizer=None, stability_layer=None,
                 meta_control_plane=None,
                 system_directive_engine=None):
        self.scheduler = scheduler
        self.executor = executor
        self.memory = memory
        self._feedback_engine = feedback_engine
        self._global_optimizer = global_optimizer
        self._stability_layer = stability_layer
        self._meta_control_plane = meta_control_plane
        self._system_directive_engine = system_directive_engine
        self._task_count = 0

    def run_task(self, task_input: str):
        task = self.scheduler.create_task(task_input)

        # ── System Directive Engine (v1) — 执行前行为控制 ──────────────
        if self._system_directive_engine is not None:
            sde_ctx = {
                "input": task_input,
                "task_count": self._task_count,
                "has_tools": True,
            }
            task.directive = self._system_directive_engine.process(task_input, sde_ctx)

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

        # === GLOBAL OPTIMIZATION 阶段（每 50 任务触发） ===
        self._task_count += 1
        if self._global_optimizer and self._task_count % 50 == 0:
            try:
                all_tasks = self.memory.get_all()
                history = []
                for t in all_tasks:
                    history.append({
                        "filtered_plan": {"steps": getattr(t, "plan", []) or []},
                        "steps": getattr(t, "plan", []) or [],
                        "success": t.status == TaskStatus.COMPLETED,
                        "passed": t.status == TaskStatus.COMPLETED,
                        "strategy": "BALANCED",
                        "strategy_used": "BALANCED",
                        "decisions": [],
                    })

                # ── Meta Control Plane: 检查是否允许优化 ──
                if self._meta_control_plane is not None:
                    sys_state = self._build_system_state(history)
                    meta_result = self._meta_control_plane.process(
                        sys_state, {"adjustments": {}}
                    )
                    if not meta_result["meta_decision"]["allowed"]:
                        return {
                            "task_id": task.id,
                            "status": task.status.value,
                            "goal": task.plan_goal,
                            "plan": task.plan,
                            "steps": task.steps,
                            "result": task.result,
                            "retry_count": task.retry_count,
                            "meta_blocked": True,
                            "meta_reason": meta_result["reason"],
                        }

                self._global_optimizer.run(history)
            except Exception:
                pass

        # === STABILITY CHECK 阶段（每 50 任务触发） ===
        if self._stability_layer and self._task_count % 50 == 0:
            try:
                stability = self._stability_layer.run(
                    optimizer_result={"adjustments": {}, "metrics": {}},
                    system_state={"strategy_effectiveness": {}, "decisions": []},
                )
                if stability["rollback"]["triggered"] \
                   and stability["rollback"]["target_snapshot"]:
                    self._stability_layer.restore_snapshot(
                        stability["rollback"]["target_snapshot"],
                    )
            except Exception:
                pass

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

    def _build_system_state(self, history: list[dict]) -> dict:
        """为 MetaControlPlane 构建系统状态摘要。"""
        # 计算 strategy 成功率
        strategy_counts: dict[str, int] = {}
        strategy_successes: dict[str, int] = {}
        total_tasks = len(history)
        for r in history:
            s = r.get("strategy", "BALANCED")
            strategy_counts[s] = strategy_counts.get(s, 0) + 1
            if r.get("success", True):
                strategy_successes[s] = strategy_successes.get(s, 0) + 1

        strategy_eff = {}
        for s, count in strategy_counts.items():
            suc = strategy_successes.get(s, 0)
            rate = suc / count if count > 0 else 0.5
            strategy_eff[s] = {
                "success_rate": round(rate, 4),
                "variance": 0.0,
                "tasks": count,
            }

        # 计算 fallback_rate
        total_decisions = sum(len(r.get("decisions", [])) for r in history)
        total_fallbacks = sum(
            1 for r in history
            for d in r.get("decisions", [])
            if d.get("action") in ("reroute", "downgrade", "block")
        )
        fallback_rate = total_fallbacks / max(total_decisions, 1)

        # 漂移信息（从 stability_layer 获取，如果有的话）
        drift = {}
        if self._stability_layer is not None:
            recent_snaps = getattr(self._stability_layer, '_optimization_history', [])
            if recent_snaps and recent_snaps[-3:].count("unstable") >= 2:
                drift = {"drift_detected": True, "severity": "medium"}
            else:
                drift = {"drift_detected": False, "severity": "none"}

        return {
            "strategy_effectiveness": strategy_eff,
            "fallback_rate": round(fallback_rate, 4),
            "total_tasks": total_tasks,
            "cost_stability": 1.0,
            "rollback_rate": 0.0,
            "drift": drift,
        }
