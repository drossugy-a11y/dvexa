class MemoryStore:
    def __init__(self):
        self.tasks = []

    def save(self, task_state):
        self.tasks.append({
            "task_id": task_state.id,
            "input": task_state.input,
            "status": task_state.status.value,
            "goal": task_state.plan_goal,
            "plan": task_state.plan,
            "steps": task_state.steps,
            "result": task_state.result,
            "retry_count": task_state.retry_count,
            "error": task_state.error,
        })
        return self.tasks[-1]

    def get_all(self):
        return self.tasks

    def get_by_id(self, task_id):
        for t in self.tasks:
            if t["task_id"] == task_id:
                return t
        return None
